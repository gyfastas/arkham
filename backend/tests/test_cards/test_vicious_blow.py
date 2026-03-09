"""Tests for Vicious Blow (Level 0)."""

from backend.cards.guardian.vicious_blow_lv0 import ViciousBlow


class TestViciousBlow:
    def test_card_id(self):
        assert ViciousBlow.card_id == "vicious_blow_lv0"

    def test_has_extra_damage_handler(self):
        """Vicious Blow should have a SKILL_TEST_SUCCESSFUL handler."""
        impl = ViciousBlow("test_instance")
        assert hasattr(impl, 'extra_damage')
