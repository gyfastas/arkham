"""Tests for Dynamite Blast (Level 0)."""

from backend.cards.guardian.dynamite_blast_lv0 import DynamiteBlast


class TestDynamiteBlast:
    def test_card_id(self):
        assert DynamiteBlast.card_id == "dynamite_blast_lv0"

    def test_skeleton_placeholder(self):
        """Dynamite Blast is a skeleton — AoE damage not yet implemented."""
        impl = DynamiteBlast("test_instance")
        assert impl.card_id == "dynamite_blast_lv0"
