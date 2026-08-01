"""Tests for SlotManager."""

import pytest
from backend.engine.slots import SlotManager
from backend.models.enums import SlotType


class TestSlotManager:
    def test_initial_all_available(self):
        mgr = SlotManager()
        assert mgr.available(SlotType.HAND) == 2
        assert mgr.available(SlotType.ARCANE) == 2
        assert mgr.available(SlotType.ALLY) == 1
        assert mgr.available(SlotType.ACCESSORY) == 1
        assert mgr.available(SlotType.BODY) == 1

    def test_occupy_reduces_availability(self):
        mgr = SlotManager()
        mgr.occupy("card_1", [SlotType.HAND])
        assert mgr.available(SlotType.HAND) == 1

    def test_occupy_two_hand_slots(self):
        mgr = SlotManager()
        mgr.occupy("card_1", [SlotType.HAND, SlotType.HAND])
        assert mgr.available(SlotType.HAND) == 0

    def test_can_play_true(self):
        mgr = SlotManager()
        assert mgr.can_play([SlotType.HAND])

    def test_can_play_false_when_full(self):
        mgr = SlotManager()
        mgr.occupy("card_1", [SlotType.HAND])
        mgr.occupy("card_2", [SlotType.HAND])
        assert not mgr.can_play([SlotType.HAND])

    def test_vacate_frees_slot(self):
        mgr = SlotManager()
        mgr.occupy("card_1", [SlotType.HAND])
        mgr.vacate("card_1")
        assert mgr.available(SlotType.HAND) == 2

    def test_slots_to_free(self):
        mgr = SlotManager()
        mgr.occupy("card_1", [SlotType.ALLY])
        result = mgr.slots_to_free([SlotType.ALLY])
        assert result == {SlotType.ALLY: 1}

    def test_no_slot_asset_unlimited(self):
        mgr = SlotManager()
        for i in range(10):
            mgr.occupy(f"card_{i}", [])
        # No slots occupied
        assert mgr.available(SlotType.HAND) == 2

    def test_get_cards_in_slot(self):
        mgr = SlotManager()
        mgr.occupy("card_1", [SlotType.HAND])
        mgr.occupy("card_2", [SlotType.HAND])
        assert mgr.get_cards_in_slot(SlotType.HAND) == ["card_1", "card_2"]


class TestRestrictedBonusSlots:
    """Tote-Bag style restricted slots: Tome-only hand slots."""

    def _tote_mgr(self) -> SlotManager:
        mgr = SlotManager()
        mgr.add_restricted_bonus(SlotType.HAND, 2, trait="tome", source="tote")
        return mgr

    def test_effective_limit_by_traits(self):
        mgr = self._tote_mgr()
        assert mgr.effective_limit(SlotType.HAND, ["tome"]) == 4
        assert mgr.effective_limit(SlotType.HAND, ["item"]) == 2
        assert mgr.effective_limit(SlotType.HAND, None) == 2

    def test_tome_card_can_use_restricted_slots(self):
        mgr = self._tote_mgr()
        mgr.occupy("w1", [SlotType.HAND], ["tome"])
        mgr.occupy("w2", [SlotType.HAND], ["tome"])
        # 2 hand slots full, but a Tome can still be played (restricted)
        assert mgr.can_play_card([SlotType.HAND], ["tome"])
        mgr.occupy("w3", [SlotType.HAND], ["tome"])
        mgr.occupy("w4", [SlotType.HAND], ["tome"])
        # All 4 (2 base + 2 restricted) used
        assert not mgr.can_play_card([SlotType.HAND], ["tome"])

    def test_non_tome_cannot_use_restricted_slots(self):
        mgr = self._tote_mgr()
        mgr.occupy("w1", [SlotType.HAND], ["tome"])
        mgr.occupy("w2", [SlotType.HAND], ["tome"])
        # Non-tome weapon: base slots are taken by... wait, tomes can sit in
        # base slots too. Non-tome count is 0 here, base is 2 → allowed.
        assert mgr.can_play_card([SlotType.HAND], ["item"])
        # Fill base slots with non-tomes instead
        mgr2 = self._tote_mgr()
        mgr2.occupy("g1", [SlotType.HAND], ["item"])
        mgr2.occupy("g2", [SlotType.HAND], ["item"])
        assert not mgr2.can_play_card([SlotType.HAND], ["item"])
        # But a tome still fits
        assert mgr2.can_play_card([SlotType.HAND], ["tome"])

    def test_non_tome_blocked_when_base_full_of_non_tomes(self):
        mgr = self._tote_mgr()
        mgr.occupy("g1", [SlotType.HAND], ["item"])
        mgr.occupy("g2", [SlotType.HAND], ["item"])
        mgr.occupy("t1", [SlotType.HAND], ["tome"])
        mgr.occupy("t2", [SlotType.HAND], ["tome"])
        # 4 hand cards in play (2 non-tome + 2 tome). Another non-tome? No.
        assert not mgr.can_play_card([SlotType.HAND], ["item"])

    def test_remove_restricted_bonus(self):
        mgr = self._tote_mgr()
        mgr.remove_restricted_bonus(SlotType.HAND, source="tote")
        assert SlotType.HAND not in mgr.restricted_bonuses
        assert mgr.effective_limit(SlotType.HAND, ["tome"]) == 2

    def test_slots_to_free_for_card(self):
        mgr = self._tote_mgr()
        mgr.occupy("g1", [SlotType.HAND], ["item"])
        mgr.occupy("g2", [SlotType.HAND], ["item"])
        # Non-tome needs 1 freed; tome needs 0
        assert mgr.slots_to_free_for_card([SlotType.HAND], ["item"]) == {
            SlotType.HAND: 1
        }
        assert mgr.slots_to_free_for_card([SlotType.HAND], ["tome"]) == {}

    def test_generic_and_restricted_stack(self):
        mgr = self._tote_mgr()
        mgr.add_bonus(SlotType.HAND, 1)  # e.g. some other effect
        assert mgr.effective_limit(SlotType.HAND, ["tome"]) == 5
        assert mgr.effective_limit(SlotType.HAND, ["item"]) == 3

    def test_vacate_clears_traits(self):
        mgr = self._tote_mgr()
        mgr.occupy("t1", [SlotType.HAND], ["tome"])
        mgr.vacate("t1")
        assert "t1" not in mgr.slot_traits

    def test_status_serialization(self):
        mgr = self._tote_mgr()
        mgr.occupy("t1", [SlotType.HAND], ["tome"])
        status = mgr.status()
        hand = status["hand"]
        assert hand["used"] == 1
        assert hand["base"] == 2
        assert hand["restricted"] == 2
        assert hand["limit"] == 4
        assert hand["restricted_traits"] == ["tome"]
        assert hand["cards"] == ["t1"]
