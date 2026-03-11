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
    skill: str
    committed_cards: list[str]
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
