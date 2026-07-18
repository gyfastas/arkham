"""Hard Knocks (Level 0) — Rogue Asset.
花费1资源：+1战斗。花费1资源：+1敏捷。
"""

from backend.cards._shared import ResourceSkillBoost
from backend.models.enums import Skill


class HardKnocks(ResourceSkillBoost):
    card_id = "hard_knocks_lv0"
    boosted_skills = (Skill.COMBAT, Skill.AGILITY)
