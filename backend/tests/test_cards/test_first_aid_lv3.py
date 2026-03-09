"""Tests for First Aid (Level 3)."""

from backend.cards.guardian.first_aid_lv3 import FirstAidLv3


class TestFirstAidLv3:
    def test_card_id(self):
        assert FirstAidLv3.card_id == "first_aid_lv3"

    def test_skeleton_placeholder(self):
        """First Aid (3) is a skeleton — activated ability not yet implemented."""
        impl = FirstAidLv3("test_instance")
        assert impl.card_id == "first_aid_lv3"
