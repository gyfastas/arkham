"""Hyperawareness (Level 0) — Seeker Asset.
[快速]花费1资源：本次技能检定+1智力。
[快速]花费1资源：本次技能检定+1敏捷。

说明：
- 与 Physical Training / Arcane Studies / Hard Knocks / Dig Deep 共用
  ResourceSkillBoost（可多次支付叠加）；UI/会话层通过 spend() 调用。
- 会话层通用激活通道暂不传送检定上下文（与上述四张天赋卡一致），
  需要会话层接线后玩家才能在 UI 中主动触发。
"""

from backend.cards._shared import ResourceSkillBoost
from backend.models.enums import Skill


class Hyperawareness(ResourceSkillBoost):
    card_id = "hyperawareness_lv0"
    boosted_skills = (Skill.INTELLECT, Skill.AGILITY)
