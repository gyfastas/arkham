"""Rite of Seeking (Level 2) — Mystic Asset, Arcane slot.
使用(3充能)。消耗礼寻术并花费1充能：调查。本次调查使用意志代替智力。
你获得+2智力，本次调查发现额外1条线索。
"""

from backend.cards.base import on_event
from backend.cards.mystic.rite_of_seeking_lv0 import RiteOfSeeking
from backend.models.enums import GameEvent, Skill, TimingPriority


class RiteOfSeekingLv2(RiteOfSeeking):
    card_id = "rite_of_seeking_lv2"
    extra_clue = True
    bad_token_penalty = False  # lv2 无负面标记惩罚

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def bonus_intellect(self, ctx):
        """额外 +2 智力（在替换意志之后叠加）。"""
        if not self._armed or ctx.skill_type != Skill.INTELLECT:
            return
        ctx.modify_amount(2, "rite_of_seeking_lv2_bonus")


# 兼容旧测试：backend/tests/test_cards/test_rite_of_seeking.py 从本模块导入该名
RiteOfSeeking = RiteOfSeekingLv2
