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
    # Extra slots granted by cards (Charisma, Relic Hunter, ...)
    bonus_slots: dict[SlotType, int] = field(default_factory=dict)
    # Restricted bonus slots: only cards with the required trait may use them
    # (e.g. Daisy's Tote Bag: 2 extra hand slots, Tome only).
    # slot_type -> [{"source": instance_id, "count": int, "trait": str}]
    restricted_bonuses: dict[SlotType, list[dict]] = field(default_factory=dict)
    # instance_id -> traits of the occupying card (for restricted-slot checks)
    slot_traits: dict[str, frozenset[str]] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Generic bonus slots
    # ------------------------------------------------------------------
    def add_bonus(self, slot_type: SlotType, count: int) -> None:
        self.bonus_slots[slot_type] = self.bonus_slots.get(slot_type, 0) + count

    def remove_bonus(self, slot_type: SlotType, count: int) -> None:
        remaining = self.bonus_slots.get(slot_type, 0) - count
        if remaining > 0:
            self.bonus_slots[slot_type] = remaining
        else:
            self.bonus_slots.pop(slot_type, None)

    # ------------------------------------------------------------------
    # Restricted bonus slots (trait-gated, e.g. Tome-only hand slots)
    # ------------------------------------------------------------------
    def add_restricted_bonus(
        self, slot_type: SlotType, count: int, trait: str, source: str
    ) -> None:
        entries = self.restricted_bonuses.setdefault(slot_type, [])
        for entry in entries:
            if entry["source"] == source:
                entry["count"] = count
                entry["trait"] = trait
                return
        entries.append({"source": source, "count": count, "trait": trait})

    def remove_restricted_bonus(self, slot_type: SlotType, source: str) -> None:
        entries = self.restricted_bonuses.get(slot_type)
        if not entries:
            return
        self.restricted_bonuses[slot_type] = [
            e for e in entries if e["source"] != source
        ]
        if not self.restricted_bonuses[slot_type]:
            self.restricted_bonuses.pop(slot_type, None)

    def _restricted_count(self, slot_type: SlotType, trait: str | None) -> int:
        """Restricted bonus usable by a card with the given traits."""
        total = 0
        for entry in self.restricted_bonuses.get(slot_type, []):
            if trait is not None and entry["trait"] == trait:
                total += entry["count"]
        return total

    def _restricted_total(self, slot_type: SlotType) -> int:
        return sum(e["count"] for e in self.restricted_bonuses.get(slot_type, []))

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def count_used(self, slot_type: SlotType) -> int:
        return len(self.slots.get(slot_type, []))

    def base_limit(self, slot_type: SlotType) -> int:
        """Slots usable by ANY card (official limit + generic bonuses)."""
        return SLOT_LIMITS.get(slot_type, 0) + self.bonus_slots.get(slot_type, 0)

    def effective_limit(self, slot_type: SlotType, traits=None) -> int:
        """Slots usable by a card with the given traits (includes restricted)."""
        limit = self.base_limit(slot_type)
        trait_set = set(traits or [])
        for entry in self.restricted_bonuses.get(slot_type, []):
            if entry["trait"] in trait_set:
                limit += entry["count"]
        return limit

    def available(self, slot_type: SlotType) -> int:
        limit = SLOT_LIMITS.get(slot_type, 0) + self.bonus_slots.get(slot_type, 0)
        return max(0, limit - self.count_used(slot_type))

    # ------------------------------------------------------------------
    # Play validation
    # ------------------------------------------------------------------
    def can_play(self, required_slots: list[SlotType]) -> bool:
        """Legacy check (no traits). Delegates to can_play_card."""
        return self.can_play_card(required_slots, None)

    def can_play_card(self, required_slots: list[SlotType], traits=None) -> bool:
        """Check if a card with the given traits can be played.

        Official rule: restricted bonus slots (e.g. Tote Bag's Tome-only
        hand slots) may only be occupied by cards with the matching trait;
        cards without the trait are limited to the base slot count.
        """
        needed: dict[SlotType, int] = {}
        for s in required_slots:
            needed[s] = needed.get(s, 0) + 1
        trait_set = set(traits or [])
        for slot_type, count in needed.items():
            used = self.count_used(slot_type)
            base = self.base_limit(slot_type)
            matching = {
                e["trait"] for e in self.restricted_bonuses.get(slot_type, [])
            }
            if matching & trait_set:
                # Card may use restricted slots: total capacity check
                if used + count > self.effective_limit(slot_type, traits):
                    return False
            else:
                # Card without the trait: must fit within base slots
                non_trait_used = sum(
                    1 for iid in self.slots.get(slot_type, [])
                    if not (matching & set(self.slot_traits.get(iid, ())))
                )
                if non_trait_used + count > base:
                    return False
                # Also cannot exceed overall capacity
                if used + count > base + self._restricted_total(slot_type):
                    return False
        return True

    def slots_to_free(self, required_slots: list[SlotType]) -> dict[SlotType, int]:
        """Calculate how many slots of each type need to be freed."""
        return self.slots_to_free_for_card(required_slots, None)

    def slots_to_free_for_card(
        self, required_slots: list[SlotType], traits=None
    ) -> dict[SlotType, int]:
        """How many cards must be discarded per slot type to play this card."""
        needed: dict[SlotType, int] = {}
        for s in required_slots:
            needed[s] = needed.get(s, 0) + 1
        to_free: dict[SlotType, int] = {}
        trait_set = set(traits or [])
        for slot_type, count in needed.items():
            matching = {
                e["trait"] for e in self.restricted_bonuses.get(slot_type, [])
            }
            if matching & trait_set:
                deficit = (
                    self.count_used(slot_type) + count
                    - self.effective_limit(slot_type, traits)
                )
            else:
                base = self.base_limit(slot_type)
                non_trait_used = sum(
                    1 for iid in self.slots.get(slot_type, [])
                    if not (matching & set(self.slot_traits.get(iid, ())))
                )
                deficit = non_trait_used + count - base
            if deficit > 0:
                to_free[slot_type] = deficit
        return to_free

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------
    def occupy(
        self, instance_id: str, required_slots: list[SlotType], traits=None
    ) -> None:
        """Place a card into the specified slots."""
        for slot_type in required_slots:
            self.slots[slot_type].append(instance_id)
        if required_slots and traits:
            self.slot_traits[instance_id] = frozenset(traits)

    def vacate(self, instance_id: str) -> None:
        """Remove a card from all slots."""
        for slot_type in SlotType:
            slots = self.slots.get(slot_type, [])
            while instance_id in slots:
                slots.remove(instance_id)
        self.slot_traits.pop(instance_id, None)

    def get_cards_in_slot(self, slot_type: SlotType) -> list[str]:
        return list(self.slots.get(slot_type, []))

    def free_slot(self, slot_type: SlotType, instance_id: str) -> bool:
        """Remove a specific card from a specific slot."""
        slots = self.slots.get(slot_type, [])
        if instance_id in slots:
            slots.remove(instance_id)
            return True
        return False

    # ------------------------------------------------------------------
    # Serialization helper
    # ------------------------------------------------------------------
    def status(self) -> dict[str, dict]:
        """Slot usage summary for client display."""
        result: dict[str, dict] = {}
        for slot_type in SlotType:
            used = self.count_used(slot_type)
            base = SLOT_LIMITS.get(slot_type, 0)
            bonus = self.bonus_slots.get(slot_type, 0)
            restricted_entries = self.restricted_bonuses.get(slot_type, [])
            restricted = sum(e["count"] for e in restricted_entries)
            limit = base + bonus + restricted
            if limit <= 0 and used <= 0:
                continue
            result[slot_type.value] = {
                "used": used,
                "base": base,
                "bonus": bonus,
                "restricted": restricted,
                "restricted_traits": [e["trait"] for e in restricted_entries],
                "limit": limit,
                "cards": self.get_cards_in_slot(slot_type),
            }
        return result


def vacate_asset_slots(game_state, instance_id: str) -> None:
    """Keep slot accounting in sync when a card leaves play outside Actions."""
    manager = getattr(game_state, "slot_managers", {}).get(
        getattr(game_state.get_card_instance(instance_id), "owner_id", ""),
    )
    if manager:
        manager.vacate(instance_id)
