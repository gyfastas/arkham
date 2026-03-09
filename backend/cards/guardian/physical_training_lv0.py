"""Physical Training (Level 0) — Guardian Asset.
花费1资源：本次技能检定+1意志力。花费1资源：本次技能检定+1战斗力。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class PhysicalTraining(CardImplementation):
    card_id = "physical_training_lv0"
    # Skeleton — requires player choice to spend resources for +1 willpower or +1 combat.
    # Full implementation needs an activated ability framework.
