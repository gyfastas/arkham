"""Tests for Extra Ammunition (Level 1)."""

from backend.cards.guardian.extra_ammunition_lv1 import ExtraAmmunition


class TestExtraAmmunition:
    def test_card_id(self):
        assert ExtraAmmunition.card_id == "extra_ammunition_lv1"

    def test_skeleton_placeholder(self):
        """Extra Ammunition is a skeleton — ammo placement not yet implemented."""
        impl = ExtraAmmunition("test_instance")
        assert impl.card_id == "extra_ammunition_lv1"
