"""Protocol definitions for server-client communication.

Defines all Socket.IO event names and message structures used between
the game server and clients.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, TypedDict


# ---------------------------------------------------------------------------
# Socket.IO event names
# ---------------------------------------------------------------------------

class ServerEvent(str, Enum):
    """Events emitted by the server to clients."""
    STATE_UPDATE = "state_update"
    ACTION_RESULT = "action_result"
    GAME_EVENT = "game_event"
    ROOM_UPDATE = "room_update"
    PENDING_CHOICE = "pending_choice"
    ERROR = "error"


class ClientEvent(str, Enum):
    """Events emitted by clients to the server."""
    CREATE_ROOM = "create_room"
    JOIN_ROOM = "join_room"
    LEAVE_ROOM = "leave_room"
    SETUP_GAME = "setup_game"
    PLAYER_ACTION = "player_action"
    END_TURN = "end_turn"
    RESOLVE_CHOICE = "resolve_choice"
    CHAT = "chat"
    LIST_CARDS = "list_cards"
    GET_INVESTIGATOR = "get_investigator"
    CAMPAIGN_UPGRADE = "campaign_upgrade"  # Edit deck between scenarios (server-settled)
    CAMPAIGN_STATE = "campaign_state"  # Request campaign state
    CAMPAIGN_NEW = "campaign_new"  # Start a new campaign (ch.1, 0 XP)
    CAMPAIGN_LIST = "campaign_list"  # List saved campaigns
    CAMPAIGN_CONTINUE = "campaign_continue"  # Load a saved campaign
    GET_CHAOS_BAG_INFO = "get_chaos_bag_info"  # Chaos bag info per campaign/difficulty
    GET_OPTIONS = "get_options"  # Read user options
    SET_OPTIONS = "set_options"  # Update user options


# ---------------------------------------------------------------------------
# Message payloads (TypedDicts for documentation; not enforced at runtime)
# ---------------------------------------------------------------------------

class SetupGamePayload(TypedDict, total=False):
    scenario_id: str
    investigator_id: str
    deck_preset: str
    deck_text: str


class PlayerActionPayload(TypedDict, total=False):
    action: str
    card_id: str
    enemy_instance_id: str
    weapon_instance_id: str
    location_id: str
    instance_id: str
    target_instance_id: str
    skill: str
    committed_cards: list[str]
    effect_card_ids: list[str]
    choice_id: str


class ActionResultPayload(TypedDict, total=False):
    success: bool
    message: str
    events: list[dict[str, Any]]
    state: dict[str, Any]


class RoomUpdatePayload(TypedDict, total=False):
    room_id: str
    players: list[dict[str, Any]]
    status: str
    seats: list[dict[str, Any]]


class ErrorPayload(TypedDict):
    message: str
    code: str
