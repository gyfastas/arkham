"""Tests for Seeking Answers (Level 2)."""

from backend.cards.seeker.seeking_answers_lv2 import SeekingAnswersLv2


class TestSeekingAnswersLv2:
    def test_card_data(self):
        impl = SeekingAnswersLv2("inst")
        assert impl.card_id == "seeking_answers_lv2"
