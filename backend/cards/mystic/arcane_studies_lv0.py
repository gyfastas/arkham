"""Arcane Studies (Level 0) — Mystic Asset.
花费1资源：+1意志。花费1资源：+1智力。
"""

from backend.cards._shared import ResourceSkillBoost
from backend.models.enums import Skill


class ArcaneStudies(ResourceSkillBoost):
    card_id = "arcane_studies_lv0"
    boosted_skills = (Skill.WILLPOWER, Skill.INTELLECT)
