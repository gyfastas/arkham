"""Inquiring Mind (Level 0) — Seeker Skill.
在进行一次检定以躲避敌人或调查时打出。你获得+2本次技能类型。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class InquiringMind(CardImplementation):
    card_id = "inquiring_mind_lv0"

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def skill_bonus(self, ctx):
        """提交到躲避(敏捷)或调查(智力)检定时：+2。"""
        if "inquiring_mind_lv0" not in ctx.committed_cards:
            return
        if ctx.skill_type not in (Skill.AGILITY, Skill.INTELLECT):
            return
        ctx.modify_amount(2, "inquiring_mind_bonus")
