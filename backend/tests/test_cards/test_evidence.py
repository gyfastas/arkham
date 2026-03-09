"""Tests for Evidence! (Level 0)."""

from backend.cards.guardian.evidence_lv0 import Evidence


class TestEvidence:
    def test_card_id(self):
        assert Evidence.card_id == "evidence_lv0"

    def test_has_discover_clue_handler(self):
        """Evidence! should have an ENEMY_DEFEATED reaction handler."""
        impl = Evidence("test_instance")
        assert hasattr(impl, 'discover_clue')
