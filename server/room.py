"""Room and lobby management for multiplayer games."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal

from server.game_session import GameSession
from server.player import PlayerSession


@dataclass
class Seat:
    """A seat in a game room."""
    seat_num: int
    player_id: str | None = None
    investigator_id: str = "daisy_walker"
    deck_preset: str = ""
    ready: bool = False


class Room:
    """A game room that manages players, seating, and the game session."""

    def __init__(self, room_id: str, host_player_id: str) -> None:
        self.room_id = room_id
        self.host_player_id = host_player_id
        self.status: Literal["lobby", "in_game", "finished"] = "lobby"
        self.seats: dict[int, Seat] = {
            i: Seat(seat_num=i) for i in range(4)  # Max 4 players
        }
        self.session: GameSession | None = None

    @property
    def players(self) -> list[str]:
        return [s.player_id for s in self.seats.values() if s.player_id is not None]

    def join(self, player_id: str) -> int | None:
        """Assign player to the first available seat. Returns seat number."""
        if self.status != "lobby":
            return None
        for seat in self.seats.values():
            if seat.player_id is None:
                seat.player_id = player_id
                return seat.seat_num
        return None  # Room full

    def leave(self, player_id: str) -> bool:
        for seat in self.seats.values():
            if seat.player_id == player_id:
                seat.player_id = None
                seat.ready = False
                return True
        return False

    def set_investigator(self, player_id: str, investigator_id: str, deck_preset: str = "") -> bool:
        for seat in self.seats.values():
            if seat.player_id == player_id:
                seat.investigator_id = investigator_id
                seat.deck_preset = deck_preset
                return True
        return False

    def set_ready(self, player_id: str, ready: bool = True) -> bool:
        for seat in self.seats.values():
            if seat.player_id == player_id:
                seat.ready = ready
                return True
        return False

    def can_start(self) -> bool:
        occupied = [s for s in self.seats.values() if s.player_id is not None]
        if not occupied:
            return False
        return all(s.ready for s in occupied)

    def start_game(self, scenario_id: str = "the_gathering") -> dict:
        """Start the game with current seat configuration."""
        if not self.can_start():
            return {"success": False, "message": "玩家未全部准备"}

        self.session = GameSession(self.room_id)
        # For now, single-player setup (Phase 4 will handle multi-player)
        occupied = [s for s in self.seats.values() if s.player_id is not None]
        seat = occupied[0]

        result = self.session.setup(
            scenario_id=scenario_id,
            investigator_id=seat.investigator_id,
            deck_preset=seat.deck_preset,
        )
        if result["success"]:
            self.status = "in_game"
        return result

    def to_dict(self) -> dict:
        """Serialize room state for clients."""
        return {
            "room_id": self.room_id,
            "host_player_id": self.host_player_id,
            "status": self.status,
            "seats": [
                {
                    "seat_num": s.seat_num,
                    "player_id": s.player_id,
                    "investigator_id": s.investigator_id,
                    "deck_preset": s.deck_preset,
                    "ready": s.ready,
                }
                for s in self.seats.values()
            ],
        }


class RoomManager:
    """Manages all game rooms."""

    def __init__(self) -> None:
        self._rooms: dict[str, Room] = {}

    def create_room(self, host_player_id: str) -> Room:
        room_id = uuid.uuid4().hex[:8]
        room = Room(room_id, host_player_id)
        room.join(host_player_id)
        self._rooms[room_id] = room
        return room

    def get_room(self, room_id: str) -> Room | None:
        return self._rooms.get(room_id)

    def remove_room(self, room_id: str) -> None:
        self._rooms.pop(room_id, None)

    def list_rooms(self) -> list[dict]:
        return [r.to_dict() for r in self._rooms.values()]
