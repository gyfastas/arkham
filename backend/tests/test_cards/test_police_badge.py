"""Tests for Police Badge (Level 2)."""

from backend.cards.guardian.police_badge_lv2 import PoliceBadge


class TestPoliceBadge:
    def test_card_id(self):
        assert PoliceBadge.card_id == "police_badge_lv2"

    def test_has_willpower_bonus_handler(self):
        """Police Badge should have a SKILL_VALUE_DETERMINED handler for willpower."""
        impl = PoliceBadge("test_instance")
        assert hasattr(impl, 'willpower_bonus')
