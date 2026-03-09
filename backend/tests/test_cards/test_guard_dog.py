"""Tests for Guard Dog (Level 0)."""

from backend.cards.guardian.guard_dog_lv0 import GuardDog


class TestGuardDog:
    def test_card_id(self):
        assert GuardDog.card_id == "guard_dog_lv0"

    def test_skeleton_placeholder(self):
        """Guard Dog is a skeleton — reaction ability not yet implemented."""
        impl = GuardDog("test_instance")
        assert impl.card_id == "guard_dog_lv0"
