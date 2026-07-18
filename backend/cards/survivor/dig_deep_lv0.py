"""Dig Deep (Level 0) — Survivor Asset.
花费1资源：+1意志。花费1资源：+1敏捷。
"""

from backend.cards._shared import ResourceSkillBoost
from backend.models.enums import Skill


class DigDeep(ResourceSkillBoost):
    card_id = "dig_deep_lv0"
    boosted_skills = (Skill.WILLPOWER, Skill.AGILITY)
