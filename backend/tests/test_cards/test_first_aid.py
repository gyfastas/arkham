"""Tests for First Aid (Level 0)."""

from backend.cards.guardian.first_aid_lv0 import FirstAid


class TestFirstAid:
    def test_card_id(self):
        assert FirstAid.card_id == "first_aid_lv0"

    def test_skeleton_placeholder(self):
        """First Aid is a skeleton — activated ability not yet implemented."""
        impl = FirstAid("test_instance")
        assert impl.card_id == "first_aid_lv0"
