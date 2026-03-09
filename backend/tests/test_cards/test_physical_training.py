"""Tests for Physical Training (Level 0)."""

from backend.cards.guardian.physical_training_lv0 import PhysicalTraining


class TestPhysicalTraining:
    def test_card_id(self):
        assert PhysicalTraining.card_id == "physical_training_lv0"

    def test_skeleton_placeholder(self):
        """Physical Training is a skeleton — activated ability not yet implemented."""
        impl = PhysicalTraining("test_instance")
        assert impl.card_id == "physical_training_lv0"
