"""Tests for Shotgun (Level 4)."""

from backend.cards.guardian.shotgun_lv4 import Shotgun


class TestShotgun:
    def test_card_id(self):
        assert Shotgun.card_id == "shotgun_lv4"

    def test_skeleton_placeholder(self):
        """Shotgun is a skeleton — variable damage not yet implemented."""
        impl = Shotgun("test_instance")
        assert impl.card_id == "shotgun_lv4"
