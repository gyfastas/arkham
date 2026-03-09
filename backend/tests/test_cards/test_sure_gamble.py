"""Tests for Sure Gamble (Level 3)."""

import pytest
from backend.cards.rogue.sure_gamble_lv3 import SureGamble


class TestSureGamble:
    def test_card_id(self):
        """Sure Gamble has correct card_id."""
        assert SureGamble.card_id == "sure_gamble_lv3"

    def test_class_exists(self):
        """Implementation class is instantiable."""
        impl = SureGamble("sg_inst")
        assert impl.instance_id == "sg_inst"
