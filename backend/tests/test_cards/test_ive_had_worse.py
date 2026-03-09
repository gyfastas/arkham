"""Tests for "I've had worse..." (Level 4)."""

from backend.cards.guardian.ive_had_worse_lv4 import IveHadWorse


class TestIveHadWorse:
    def test_card_id(self):
        assert IveHadWorse.card_id == "ive_had_worse_lv4"

    def test_skeleton_placeholder(self):
        """"I've had worse..." is a skeleton — damage cancellation not yet implemented."""
        impl = IveHadWorse("test_instance")
        assert impl.card_id == "ive_had_worse_lv4"
