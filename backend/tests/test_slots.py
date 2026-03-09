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
