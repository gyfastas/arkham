"""Tests for Opportunist (Level 0)."""

import pytest
from backend.cards.rogue.opportunist_lv0 import Opportunist


class TestOpportunist:
    def test_card_id(self):
        """Opportunist has correct card_id."""
        assert Opportunist.card_id == "opportunist_lv0"

    def test_class_exists(self):
        """Implementation class is instantiable."""
        impl = Opportunist("opp_inst")
        assert impl.instance_id == "opp_inst"
