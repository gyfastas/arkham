"""Physical Training (Level 0) — Guardian Asset.
花费1资源：本次技能检定+1意志。花费1资源：本次技能检定+1战斗。
"""

from backend.cards._shared import ResourceSkillBoost
from backend.models.enums import Skill


class PhysicalTraining(ResourceSkillBoost):
    card_id = "physical_training_lv0"
    boosted_skills = (Skill.WILLPOWER, Skill.COMBAT)
