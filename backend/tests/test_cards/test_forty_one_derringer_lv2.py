"""Tests for .41 Derringer (Level 2)."""

import pytest
from backend.cards.rogue.forty_one_derringer_lv2 import FortyOneDerringerLv2


class TestFortyOneDerringerLv2:
    def test_card_id(self):
        """.41 Derringer lv2 has correct card_id."""
        assert FortyOneDerringerLv2.card_id == "forty_one_derringer_lv2"

    def test_class_exists(self):
        """Implementation class is instantiable."""
        impl = FortyOneDerringerLv2("d2_inst")
        assert impl.instance_id == "d2_inst"
