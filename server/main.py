#!/usr/bin/env python3
"""Arkham Horror LCG — Socket.IO game server.

Usage::

    python3 server/main.py [--port 8910] [--host 0.0.0.0]

Serves:
- Socket.IO at ``/socket.io/``
- Static files from ``client/dist/`` (production) or proxied by Vite (dev)
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from pathlib import Path

import socketio
from aiohttp import web

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from server.player import PlayerSession
from server.room import RoomManager
from server.protocol import ServerEvent, ClientEvent

logger = logging.getLogger("arkham.server")

# ---------------------------------------------------------------------------
# Socket.IO server
# ---------------------------------------------------------------------------

sio = socketio.AsyncServer(
    async_mode="aiohttp",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)

room_manager = RoomManager()
players: dict[str, PlayerSession] = {}  # sid -> PlayerSession


# ---------------------------------------------------------------------------
# Connection lifecycle
# ---------------------------------------------------------------------------

@sio.event
async def connect(sid: str, environ: dict):
    player_id = uuid.uuid4().hex[:12]
    player = PlayerSession(player_id=player_id, display_name=f"Player-{player_id[:4]}", sid=sid)
    players[sid] = player
    logger.info("Connected: %s (player_id=%s)", sid, player_id)
    await sio.emit("welcome", {"player_id": player_id, "rooms": room_manager.list_rooms()}, to=sid)


@sio.event
async def disconnect(sid: str):
    player = players.pop(sid, None)
    if player and player.room_id:
        room = room_manager.get_room(player.room_id)
        if room:
            room.leave(player.player_id)
            await sio.emit(
                ServerEvent.ROOM_UPDATE.value,
                room.to_dict(),
                room=player.room_id,
            )
            # Clean up empty rooms
            if not room.players:
                room_manager.remove_room(room.room_id)
    logger.info("Disconnected: %s", sid)


# ---------------------------------------------------------------------------
# Room management
# ---------------------------------------------------------------------------

@sio.on(ClientEvent.CREATE_ROOM.value)
async def on_create_room(sid: str, data: dict = None):
    player = players.get(sid)
    if not player:
        await sio.emit(ServerEvent.ERROR.value, {"message": "未连接", "code": "not_connected"}, to=sid)
        return

    room = room_manager.create_room(player.player_id)
    player.room_id = room.room_id
    await sio.enter_room(sid, room.room_id)
    await sio.emit(ServerEvent.ROOM_UPDATE.value, room.to_dict(), to=sid)
    logger.info("Room created: %s by %s", room.room_id, player.player_id)


@sio.on(ClientEvent.JOIN_ROOM.value)
async def on_join_room(sid: str, data: dict):
    player = players.get(sid)
    if not player:
        await sio.emit(ServerEvent.ERROR.value, {"message": "未连接", "code": "not_connected"}, to=sid)
        return

    room_id = data.get("room_id")
    room = room_manager.get_room(room_id)
    if not room:
        await sio.emit(ServerEvent.ERROR.value, {"message": "房间不存在", "code": "room_not_found"}, to=sid)
        return

    seat_num = room.join(player.player_id)
    if seat_num is None:
        await sio.emit(ServerEvent.ERROR.value, {"message": "房间已满", "code": "room_full"}, to=sid)
        return

    player.room_id = room.room_id
    await sio.enter_room(sid, room.room_id)
    await sio.emit(ServerEvent.ROOM_UPDATE.value, room.to_dict(), room=room.room_id)
    logger.info("Player %s joined room %s (seat %d)", player.player_id, room_id, seat_num)


@sio.on(ClientEvent.LEAVE_ROOM.value)
async def on_leave_room(sid: str, data: dict = None):
    player = players.get(sid)
    if not player or not player.room_id:
        return

    room = room_manager.get_room(player.room_id)
    if room:
        room.leave(player.player_id)
        await sio.leave_room(sid, room.room_id)
        await sio.emit(ServerEvent.ROOM_UPDATE.value, room.to_dict(), room=room.room_id)
        if not room.players:
            room_manager.remove_room(room.room_id)
    player.room_id = None


# ---------------------------------------------------------------------------
# Game setup and play
# ---------------------------------------------------------------------------

@sio.on(ClientEvent.LIST_CARDS.value)
async def on_list_cards(sid: str, data: dict = None):
    """Return available player cards for deck building."""
    from server.game_session import list_available_cards
    investigator_id = (data or {}).get("investigator_id", "")
    xp = (data or {}).get("xp", 0)
    result = list_available_cards(investigator_id, xp_available=xp)
    await sio.emit("card_list", result, to=sid)


@sio.on(ClientEvent.GET_INVESTIGATOR.value)
async def on_get_investigator(sid: str, data: dict = None):
    """Return investigator detail for client display."""
    from server.game_session import get_investigator_detail
    inv_id = (data or {}).get("investigator_id", "")
    detail = get_investigator_detail(inv_id)
    if detail:
        await sio.emit("investigator_detail", detail, to=sid)
    else:
        await sio.emit(ServerEvent.ERROR.value,
                       {"message": f"未找到调查员: {inv_id}", "code": "inv_not_found"}, to=sid)


@sio.on(ClientEvent.SETUP_GAME.value)
async def on_setup_game(sid: str, data: dict):
    player = players.get(sid)
    if not player or not player.room_id:
        await sio.emit(ServerEvent.ERROR.value, {"message": "不在房间中", "code": "not_in_room"}, to=sid)
        return

    room = room_manager.get_room(player.room_id)
    if not room:
        await sio.emit(ServerEvent.ERROR.value, {"message": "房间不存在", "code": "room_not_found"}, to=sid)
        return

    # For now, auto-ready the player and start
    room.set_investigator(
        player.player_id,
        data.get("investigator_id", "daisy_walker"),
        data.get("deck_preset", ""),
    )
    # Store custom deck cards if provided
    deck_cards = data.get("deck_cards")
    if deck_cards:
        room.set_deck_cards(player.player_id, deck_cards)
    room.set_ready(player.player_id, True)

    # Campaign mode: save_id → deck/trauma/difficulty/chapter from the save
    campaign = None
    save_id = data.get("save_id", "")
    if save_id:
        from server.campaign import load_campaign
        campaign = load_campaign(save_id)
        if campaign is None:
            await sio.emit(ServerEvent.ERROR.value, {"message": "战役存档不存在", "code": "save_not_found"}, to=sid)
            return
        scenario_id = campaign.current_scenario_id()
        if not scenario_id:
            await sio.emit(ServerEvent.ERROR.value, {"message": "战役已完结", "code": "campaign_complete"}, to=sid)
            return
        room.campaign = campaign
    else:
        scenario_id = data.get("scenario_id", "the_gathering")
    difficulty = data.get("difficulty", "standard")

    try:
        result = room.start_game(
            scenario_id=scenario_id,
            difficulty=difficulty,
            campaign_state=campaign,
        )
    except Exception as e:
        logger.exception("Failed to start game in room %s", room.room_id)
        await sio.emit(ServerEvent.ERROR.value, {"message": str(e), "code": "setup_failed"}, to=sid)
        return

    if not result["success"]:
        await sio.emit(ServerEvent.ERROR.value, {"message": result["message"], "code": "setup_failed"}, to=sid)
        return

    if campaign is not None:
        room.session.campaign = campaign

    # Add player to session
    player.investigator_ids = ["player"]
    room.session.add_player(player)

    # Broadcast initial state to all players in room
    try:
        state = room.session.get_state_for_player(player.player_id)
    except Exception as e:
        logger.exception("Failed to serialize state")
        await sio.emit(ServerEvent.ERROR.value, {"message": str(e), "code": "state_error"}, to=sid)
        return

    await sio.emit(
        ServerEvent.STATE_UPDATE.value,
        {"state": state},
        room=room.room_id,
    )
    logger.info("Game started in room %s", room.room_id)


@sio.on(ClientEvent.PLAYER_ACTION.value)
async def on_player_action(sid: str, data: dict):
    player = players.get(sid)
    if not player or not player.room_id:
        await sio.emit(ServerEvent.ERROR.value, {"message": "不在游戏中", "code": "not_in_game"}, to=sid)
        return

    room = room_manager.get_room(player.room_id)
    if not room or not room.session:
        await sio.emit(ServerEvent.ERROR.value, {"message": "游戏未开始", "code": "game_not_started"}, to=sid)
        return

    result = room.session.handle_action(player.player_id, data)
    state = room.session.get_state_for_player(player.player_id)
    result["state"] = state

    # Send result to acting player
    await sio.emit(ServerEvent.ACTION_RESULT.value, result, to=sid)

    # Broadcast updated state to all other players in room
    # (In Phase 4, each player gets their own filtered state)
    await sio.emit(
        ServerEvent.STATE_UPDATE.value,
        {"state": state, "events": result.get("events", [])},
        room=room.room_id,
        skip_sid=sid,
    )


@sio.on(ClientEvent.END_TURN.value)
async def on_end_turn(sid: str, data: dict = None):
    player = players.get(sid)
    if not player or not player.room_id:
        await sio.emit(ServerEvent.ERROR.value, {"message": "不在游戏中", "code": "not_in_game"}, to=sid)
        return

    room = room_manager.get_room(player.room_id)
    if not room or not room.session:
        await sio.emit(ServerEvent.ERROR.value, {"message": "游戏未开始", "code": "game_not_started"}, to=sid)
        return

    result = room.session.handle_end_turn(player.player_id)
    state = room.session.get_state_for_player(player.player_id)
    result["state"] = state

    await sio.emit(ServerEvent.ACTION_RESULT.value, result, to=sid)
    await sio.emit(
        ServerEvent.STATE_UPDATE.value,
        {"state": state, "events": result.get("events", [])},
        room=room.room_id,
        skip_sid=sid,
    )


@sio.on(ClientEvent.RESOLVE_CHOICE.value)
async def on_resolve_choice(sid: str, data: dict):
    """Shortcut for RESOLVE_CHOICE action."""
    data["action"] = "RESOLVE_CHOICE"
    await on_player_action(sid, data)


@sio.on(ClientEvent.CAMPAIGN_STATE.value)
async def on_campaign_state(sid: str, data: dict = None):
    """Return current campaign state to client."""
    player = players.get(sid)
    if not player or not player.room_id:
        await sio.emit(ServerEvent.ERROR.value, {"message": "不在房间中", "code": "not_in_room"}, to=sid)
        return

    room = room_manager.get_room(player.room_id)
    if not room:
        return

    if room.campaign:
        await sio.emit("campaign_state", room.campaign.to_dict(), to=sid)
    else:
        await sio.emit("campaign_state", None, to=sid)


@sio.on(ClientEvent.CAMPAIGN_UPGRADE.value)
async def on_campaign_upgrade(sid: str, data: dict):
    """Edit the campaign deck between scenarios (server-authoritative).

    data: {"save_id": str, "new_deck": [card_id, ...]  # exactly 30 cards}
    XP cost is settled server-side from the deck diff (official rules:
    upgrade = level difference min 1, new card = level min 1, removal free).
    """
    from server.campaign import load_campaign, save_campaign

    save_id = (data or {}).get("save_id", "")
    new_deck = (data or {}).get("new_deck") or []
    camp = load_campaign(save_id)
    if camp is None:
        await sio.emit(ServerEvent.ERROR.value, {"message": "战役存档不存在", "code": "save_not_found"}, to=sid)
        return

    # Card DB for name/level lookup
    from backend.engine.game import Game
    from server.game_session import _load_player_cards
    g = Game("upgrade_check")
    _load_player_cards(g)

    ok, msg, cost = camp.apply_deck_change(new_deck, g.state.card_database)
    if not ok:
        await sio.emit(ServerEvent.ERROR.value, {"message": msg, "code": "xp_insufficient"}, to=sid)
        return
    save_campaign(camp)
    result = camp.to_dict()
    result["upgrade_message"] = msg
    result["upgrade_cost"] = cost
    await sio.emit("campaign_state", result, to=sid)


@sio.on(ClientEvent.CAMPAIGN_NEW.value)
async def on_campaign_new(sid: str, data: dict):
    """Create a new campaign save (chapter 1, 0 XP).

    data: {"campaign_id": str, "investigator_id": str, "difficulty": str,
           "deck_cards": [card_id, ...]}
    """
    from server.campaign import campaign_scenarios, new_campaign

    campaign_id = (data or {}).get("campaign_id", "core")
    investigator_id = (data or {}).get("investigator_id", "daisy_walker")
    difficulty = (data or {}).get("difficulty", "standard")
    deck = (data or {}).get("deck_cards") or []

    if not campaign_scenarios(campaign_id):
        await sio.emit(ServerEvent.ERROR.value, {"message": f"未知战役: {campaign_id}", "code": "bad_campaign"}, to=sid)
        return
    if difficulty not in ("easy", "standard", "hard", "expert"):
        difficulty = "standard"
    if len(deck) != 30:
        await sio.emit(ServerEvent.ERROR.value, {"message": "战役开局牌组必须为 30 张", "code": "bad_deck"}, to=sid)
        return

    camp = new_campaign(campaign_id, investigator_id, difficulty, deck)
    logger.info("Campaign created: %s (%s/%s)", camp.save_id, campaign_id, difficulty)
    await sio.emit("campaign_state", camp.to_dict(), to=sid)


@sio.on(ClientEvent.CAMPAIGN_LIST.value)
async def on_campaign_list(sid: str, data: dict = None):
    from server.campaign import list_campaigns
    await sio.emit("campaign_list", {"campaigns": list_campaigns()}, to=sid)


@sio.on(ClientEvent.CAMPAIGN_CONTINUE.value)
async def on_campaign_continue(sid: str, data: dict):
    """Load a saved campaign; returns its state (client then starts the
    current chapter via SETUP_GAME with save_id).

    data: {"save_id": str, "advance": bool} — advance=true moves to the
    next chapter (used after settlement at chapter end).
    """
    from server.campaign import load_campaign, save_campaign

    save_id = (data or {}).get("save_id", "")
    camp = load_campaign(save_id)
    if camp is None:
        await sio.emit(ServerEvent.ERROR.value, {"message": "战役存档不存在", "code": "save_not_found"}, to=sid)
        return
    if (data or {}).get("advance"):
        camp.advance_scenario()
        save_campaign(camp)
    await sio.emit("campaign_state", camp.to_dict(), to=sid)


@sio.on(ClientEvent.GET_CHAOS_BAG_INFO.value)
async def on_chaos_bag_info(sid: str, data: dict = None):
    """Chaos bag composition + symbol effect text for a campaign/difficulty."""
    from backend.models.chaos import bag_summary, load_chaos_bag_data

    campaign = (data or {}).get("campaign", "core")
    difficulty = (data or {}).get("difficulty", "standard")
    info = bag_summary(campaign, difficulty)
    data_all = load_chaos_bag_data()
    info["difficulty_labels"] = data_all.get("difficulty_labels", {})
    info["campaign_name_cn"] = (
        (data_all.get("campaigns", {}).get(campaign) or {}).get("name_cn", campaign)
    )
    # Symbol effect text (Standard side) from the encounter DB scenario cards
    try:
        from backend.scenarios.official_core import load_encounter_db_for_campaign
        db = load_encounter_db_for_campaign(campaign)
        texts = {}
        for card in db.values():
            if card.get("type") == "scenario":
                texts[card.get("encounter_code") or card["id"]] = card.get("text_cn") or card.get("text") or ""
        info["symbol_texts"] = texts
    except Exception:
        info["symbol_texts"] = {}
    await sio.emit("chaos_bag_info", info, to=sid)



# ---------------------------------------------------------------------------
# HTTP app
# ---------------------------------------------------------------------------

def create_app() -> web.Application:
    app = web.Application()
    sio.attach(app)

    # Serve static files from client/dist if present
    client_dist = PROJECT_ROOT / "client" / "dist"
    if client_dist.is_dir():
        index_file = client_dist / "index.html"

        async def index(_request: web.Request) -> web.FileResponse:
            return web.FileResponse(index_file)

        # Exact route for "/" must be registered before the static prefix,
        # otherwise aiohttp shows a directory listing instead of the app.
        app.router.add_get("/", index)
        app.router.add_static("/", client_dist, show_index=False)

    return app


def main():
    parser = argparse.ArgumentParser(description="Arkham Horror LCG Game Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8910, help="Port to listen on")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    app = create_app()
    logger.info("Starting Arkham Horror LCG server on %s:%d", args.host, args.port)
    web.run_app(app, host=args.host, port=args.port, print=None)


if __name__ == "__main__":
    main()
