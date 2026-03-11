"""Player session management."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PlayerSession:
    """Represents a connected player."""
    player_id: str
    display_name: str
    sid: str  # Socket.IO session id
    room_id: str | None = None
    investigator_ids: list[str] = field(default_factory=list)

    @property
    def is_in_room(self) -> bool:
        return self.room_id is not None
