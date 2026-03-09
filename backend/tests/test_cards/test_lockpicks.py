"""Tests for Lockpicks (Level 1)."""

import pytest
from backend.cards.rogue.lockpicks_lv1 import Lockpicks


class TestLockpicks:
    def test_card_id(self):
        """Lockpicks has correct card_id."""
        assert Lockpicks.card_id == "lockpicks_lv1"

    def test_class_exists(self):
        """Implementation class is instantiable."""
        impl = Lockpicks("lp_inst")
        assert impl.instance_id == "lp_inst"
