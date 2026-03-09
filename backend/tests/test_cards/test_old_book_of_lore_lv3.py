"""Tests for Old Book of Lore (Level 3)."""

from backend.cards.seeker.old_book_of_lore_lv3 import OldBookOfLoreLv3


class TestOldBookOfLoreLv3:
    def test_card_data(self):
        impl = OldBookOfLoreLv3("inst")
        assert impl.card_id == "old_book_of_lore_lv3"
