"""Asset slot management for investigators."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from backend.models.enums import SLOT_LIMITS, SlotType

if TYPE_CHECKING:
    from backend.models.state import GameState


@dataclass
class SlotManager:
    """Manages asset slots for a single investigator."""
    # slot_type -> list of card instance_ids occupying that slot
    slots: dict[SlotType, list[str]] = field(default_factory=lambda: {
        st: [] for st in SlotType
    })

    def count_used(self, slot_type: SlotType) -> int:
        return len(self.slots.get(slot_type, []))

    def available(self, slot_type: SlotType) -> int:
        limit = SLOT_LIMITS.get(slot_type, 0)
        return max(0, limit - self.count_used(slot_type))

    def can_play(self, required_slots: list[SlotType]) -> bool:
        """Check if slots are available (ignoring discard option)."""
        needed: dict[SlotType, int] = {}
        for s in required_slots:
            needed[s] = needed.get(s, 0) + 1
        for slot_type, count in needed.items():
            if self.available(slot_type) < count:
                return False
        return True

    def slots_to_free(self, required_slots: list[SlotType]) -> dict[SlotType, int]:
        """Calculate how many slots of each type need to be freed."""
        needed: dict[SlotType, int] = {}
        for s in required_slots:
            needed[s] = needed.get(s, 0) + 1
        to_free: dict[SlotType, int] = {}
        for slot_type, count in needed.items():
            deficit = count - self.available(slot_type)
            if deficit > 0:
                to_free[slot_type] = deficit
        return to_free

    def occupy(self, instance_id: str, required_slots: list[SlotType]) -> None:
        """Place a card into the specified slots."""
        for slot_type in required_slots:
            self.slots[slot_type].append(instance_id)

    def vacate(self, instance_id: str) -> None:
        """Remove a card from all slots."""
        for slot_type in SlotType:
            slots = self.slots.get(slot_type, [])
            while instance_id in slots:
                slots.remove(instance_id)

    def get_cards_in_slot(self, slot_type: SlotType) -> list[str]:
        return list(self.slots.get(slot_type, []))

    def free_slot(self, slot_type: SlotType, instance_id: str) -> bool:
        """Remove a specific card from a specific slot."""
        slots = self.slots.get(slot_type, [])
        if instance_id in slots:
            slots.remove(instance_id)
            return True
        return False
