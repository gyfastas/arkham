"""Tests for Dodge (Level 0)."""

from backend.cards.guardian.dodge_lv0 import Dodge


class TestDodge:
    def test_card_id(self):
        assert Dodge.card_id == "dodge_lv0"

    def test_skeleton_placeholder(self):
        """Dodge is a skeleton — attack cancellation not yet implemented."""
        impl = Dodge("test_instance")
        assert impl.card_id == "dodge_lv0"
