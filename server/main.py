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
    room.set_ready(player.player_id, True)

    try:
        result = room.start_game(scenario_id=data.get("scenario_id", "the_gathering"))
    except Exception as e:
        logger.exception("Failed to start game in room %s", room.room_id)
        await sio.emit(ServerEvent.ERROR.value, {"message": str(e), "code": "setup_failed"}, to=sid)
        return

    if not result["success"]:
        await sio.emit(ServerEvent.ERROR.value, {"message": result["message"], "code": "setup_failed"}, to=sid)
        return

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


# ---------------------------------------------------------------------------
# HTTP app
# ---------------------------------------------------------------------------

def create_app() -> web.Application:
    app = web.Application()
    sio.attach(app)

    # Serve static files from client/dist if present
    client_dist = PROJECT_ROOT / "client" / "dist"
    if client_dist.is_dir():
        app.router.add_static("/", client_dist, show_index=True)

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
