"""Game state serialization for server-client communication.

Extracted from ``frontend/server_core.py`` so that both the legacy HTTP
servers and the new Socket.IO server share one canonical serializer.

Three levels of serialization:

* ``serialize_game_state(game, ...)`` — full state (backward-compatible
  with the old ``serialize_state``).
* ``serialize_public_state(game)`` — board state visible to all players.
* ``serialize_private_state(game, investigator_id)`` — hand / deck info
  for one investigator.
"""

from __future__ import annotations

from typing import Any

from backend.engine.game import Game
from backend.models.state import CardData
from backend.scenarios.official_core import load_scenario_definition


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _enemy_dict(game: Game, ci: Any, cd: CardData | None, engaged: bool) -> dict:
    return {
        "instance_id": ci.instance_id,
        "id": ci.card_id,
        "name": cd.name if cd else ci.card_id,
        "name_cn": cd.name_cn if cd else "",
        "fight": cd.enemy_fight if cd else 0,
        "health": cd.enemy_health if cd else 0,
        "evade": cd.enemy_evade if cd else 0,
        "damage_dealt": cd.enemy_damage if cd else 0,
        "horror_dealt": cd.enemy_horror if cd else 0,
        "current_damage": ci.damage,
        "exhausted": ci.exhausted,
        "engaged": engaged,
    }


def _serialize_card(cd: CardData) -> dict:
    """Serialize a CardData for hand / catalog display."""
    return {
        "id": cd.id,
        "name": cd.name,
        "name_cn": cd.name_cn,
        "type": cd.type.value,
        "cost": cd.cost,
        "text": cd.text,
        "class": cd.card_class.value if cd.card_class else "neutral",
        "slots": [s.value for s in cd.slots],
        "skill_icons": cd.skill_icons,
        "traits": cd.traits,
    }


def _serialize_card_instance(game: Game, ci: Any) -> dict:
    """Serialize a CardInstance in play area."""
    cd = game.state.get_card_data(ci.card_id)
    return {
        "instance_id": ci.instance_id,
        "id": ci.card_id,
        "name": cd.name if cd else ci.card_id,
        "name_cn": cd.name_cn if cd else "",
        "exhausted": ci.exhausted,
        "uses": ci.uses,
        "slots": [s.value for s in ci.slot_used],
        "traits": list(cd.traits) if cd else [],
    }


# ---------------------------------------------------------------------------
# Public state (visible to all players)
# ---------------------------------------------------------------------------

def serialize_public_state(game: Game) -> dict:
    """Serialize the board state visible to all players.

    Includes: locations, enemies at locations, doom/act/agenda, round/phase,
    victory display, and scenario info.
    """
    scenario = game.state.scenario
    scen_def = load_scenario_definition(scenario.scenario_id)

    # Locations
    locations: dict[str, dict] = {}
    for loc_id, loc in game.state.locations.items():
        locations[loc_id] = {
            "name": loc.card_data.name,
            "name_cn": loc.card_data.name_cn,
            "shroud": loc.shroud,
            "clues": loc.clues,
            "connections": loc.connections,
            "enemies_here": len(loc.enemies),
        }

    # Act / Agenda
    act = scenario.current_act
    agenda = scenario.current_agenda
    act_need = act.clue_threshold if act and act.clue_threshold is not None else 0
    doom_threshold = agenda.doom_threshold if agenda else scenario.doom_threshold

    return {
        "locations": locations,
        "round": scenario.round_number,
        "phase": scenario.current_phase.name,
        "doom": scenario.doom_on_agenda,
        "doom_threshold": doom_threshold,
        "total_clues_needed": act_need,
        "scenario": {
            "id": scenario.scenario_id,
            "name": scen_def.get("name"),
            "name_cn": scen_def.get("name_cn"),
            "act": {
                "id": act.id,
                "name": act.name,
                "name_cn": act.name_cn,
                "clues": act_need,
            } if act else None,
            "agenda": {
                "id": agenda.id,
                "name": agenda.name,
                "name_cn": agenda.name_cn,
                "doom": doom_threshold,
            } if agenda else None,
            "resolution_id": scenario.vars.get("resolution_id"),
        },
    }


# ---------------------------------------------------------------------------
# Investigator serialization
# ---------------------------------------------------------------------------

def serialize_investigator_public(game: Game, investigator_id: str) -> dict:
    """Public info for an investigator (visible to all players)."""
    inv = game.state.get_investigator(investigator_id)
    if inv is None:
        return {}

    # Play area (face-up assets)
    play_area = []
    for iid in inv.play_area:
        ci = game.state.get_card_instance(iid)
        if ci:
            play_area.append(_serialize_card_instance(game, ci))

    # Threat area (engaged enemies)
    threat_area = []
    for iid in list(inv.threat_area):
        ci = game.state.get_card_instance(iid)
        if ci:
            cd = game.state.get_card_data(ci.card_id)
            threat_area.append(_enemy_dict(game, ci, cd, engaged=True))

    return {
        "id": inv.card_data.id,
        "name": inv.card_data.name,
        "name_cn": inv.card_data.name_cn,
        "class": inv.card_data.card_class.value,
        "health": inv.health,
        "sanity": inv.sanity,
        "damage": inv.damage,
        "horror": inv.horror,
        "resources": inv.resources,
        "clues": inv.clues,
        "actions_remaining": inv.actions_remaining,
        "tome_actions_remaining": inv.tome_actions_remaining,
        "hand_count": len(inv.hand),
        "deck_count": len(inv.deck),
        "discard_count": len(inv.discard),
        "defeated": inv.is_defeated,
        "location_id": inv.location_id,
        "play_area": play_area,
        "threat_area": threat_area,
    }


def serialize_private_state(game: Game, investigator_id: str) -> dict:
    """Private info for an investigator (hand cards, etc.)."""
    inv = game.state.get_investigator(investigator_id)
    if inv is None:
        return {}

    hand = []
    for card_id in inv.hand:
        cd = game.state.get_card_data(card_id)
        if cd:
            hand.append(_serialize_card(cd))

    return {
        "hand": hand,
    }


# ---------------------------------------------------------------------------
# Full state (backward compatible with server_core.serialize_state)
# ---------------------------------------------------------------------------

def serialize_game_state(
    game: Game,
    *,
    action_log: list[str] | None = None,
    game_over: dict | None = None,
    viewer_investigator_id: str = "player",
) -> dict:
    """Serialize full game state, backward-compatible with the legacy format.

    Parameters
    ----------
    game : Game
        The game instance.
    action_log : list[str], optional
        Action log entries to include.
    game_over : dict, optional
        Game over info (``{"type": "win"|"lose", "message": "..."}``).
    viewer_investigator_id : str
        The investigator whose private info (hand) should be included.
        Defaults to ``"player"`` for backward compat with single-player.
    """
    inv = game.state.get_investigator(viewer_investigator_id)
    cur_loc = game.state.get_location(inv.location_id) if inv else None
    scenario = game.state.scenario
    scen_def = load_scenario_definition(scenario.scenario_id)

    # Locations (with is_current for the viewing investigator)
    locations: dict[str, dict] = {}
    for loc_id, loc in game.state.locations.items():
        locations[loc_id] = {
            "name": loc.card_data.name,
            "name_cn": loc.card_data.name_cn,
            "shroud": loc.shroud,
            "clues": loc.clues,
            "connections": loc.connections,
            "enemies_here": len(loc.enemies),
            "is_current": inv is not None and loc_id == inv.location_id,
        }

    # Hand (private)
    hand: list[dict] = []
    if inv:
        for card_id in inv.hand:
            cd = game.state.get_card_data(card_id)
            if cd:
                hand.append(_serialize_card(cd))

    # Play area
    play_area: list[dict] = []
    if inv:
        for iid in inv.play_area:
            ci = game.state.get_card_instance(iid)
            if ci:
                play_area.append(_serialize_card_instance(game, ci))

    # Enemies (engaged + at current location)
    enemies: list[dict] = []
    if inv:
        for iid in list(inv.threat_area):
            ci = game.state.get_card_instance(iid)
            if ci:
                cd = game.state.get_card_data(ci.card_id)
                enemies.append(_enemy_dict(game, ci, cd, engaged=True))
    if cur_loc:
        for iid in list(cur_loc.enemies):
            ci = game.state.get_card_instance(iid)
            if ci:
                cd = game.state.get_card_data(ci.card_id)
                enemies.append(_enemy_dict(game, ci, cd, engaged=False))

    # Act / Agenda
    act = scenario.current_act
    agenda = scenario.current_agenda
    act_need = act.clue_threshold if act and act.clue_threshold is not None else 0
    doom_threshold = agenda.doom_threshold if agenda else scenario.doom_threshold

    # Treacheries / pending choice
    tre = scenario.vars.get("treacheries", {})
    tre_list = sorted(list(tre.values()), key=lambda x: x.get("id", ""))
    pending_choice = scenario.vars.get("pending_choice")

    return {
        "investigator": {
            "id": inv.card_data.id if inv else "",
            "name": inv.card_data.name if inv else "",
            "name_cn": inv.card_data.name_cn if inv else "",
            "class": inv.card_data.card_class.value if inv else "",
            "health": inv.health if inv else 0,
            "sanity": inv.sanity if inv else 0,
            "damage": inv.damage if inv else 0,
            "horror": inv.horror if inv else 0,
            "resources": inv.resources if inv else 0,
            "clues": inv.clues if inv else 0,
            "actions_remaining": inv.actions_remaining if inv else 0,
            "tome_actions_remaining": inv.tome_actions_remaining if inv else 0,
            "hand_count": len(inv.hand) if inv else 0,
            "deck_count": len(inv.deck) if inv else 0,
            "discard_count": len(inv.discard) if inv else 0,
            "defeated": inv.is_defeated if inv else False,
            "location_id": inv.location_id if inv else "",
        },
        "location": {
            "id": inv.location_id if inv else "",
            "name": cur_loc.card_data.name if cur_loc else "",
            "name_cn": cur_loc.card_data.name_cn if cur_loc else "",
            "shroud": cur_loc.shroud if cur_loc else 0,
            "clues": cur_loc.clues if cur_loc else 0,
            "connections": cur_loc.connections if cur_loc else [],
        },
        "locations": locations,
        "hand": hand,
        "play_area": play_area,
        "enemies": enemies,
        "log": (action_log or [])[-200:],
        "round": scenario.round_number,
        "phase": scenario.current_phase.name,
        "doom": scenario.doom_on_agenda,
        "doom_threshold": doom_threshold,
        "total_clues_needed": act_need,
        "scenario": {
            "id": scenario.scenario_id,
            "name": scen_def.get("name"),
            "name_cn": scen_def.get("name_cn"),
            "act": {
                "id": act.id,
                "name": act.name,
                "name_cn": act.name_cn,
                "clues": act_need,
            } if act else None,
            "agenda": {
                "id": agenda.id,
                "name": agenda.name,
                "name_cn": agenda.name_cn,
                "doom": doom_threshold,
            } if agenda else None,
            "resolution_id": scenario.vars.get("resolution_id"),
        },
        "treacheries": tre_list,
        "pending_choice": pending_choice,
        "game_over": game_over,
    }
