"""Rite of Seeking (Level 2) — Mystic Asset, Arcane slot. (51007)
使用(3充能)。[action]花费1充能：调查。这次调查不使用[intellect]，改为使用[willpower]。
本次检定你获得+2[willpower]。如果成功，额外发现所在地点1个线索。如果检定中抽出
[skull]、[cultist]、[tablet]、[elder_thing]或[auto_fail]标记，在检定结束后，
失去所有剩余行动，并立刻结束你的回合。
"""

from backend.cards.base import on_event
from backend.cards.mystic.rite_of_seeking_lv0 import RiteOfSeeking
from backend.models.enums import GameEvent, Skill, TimingPriority


class RiteOfSeekingLv2(RiteOfSeeking):
    card_id = "rite_of_seeking_lv2"
    extra_clue = True
    bad_token_penalty = True  # lv2 仍保留负面标记惩罚（51007 卡面）

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def bonus_willpower(self, ctx):
        """额外 +2（在替换意志之后叠加）。"""
        if not self._armed or ctx.skill_type != Skill.INTELLECT:
            return
        ctx.modify_amount(2, "rite_of_seeking_lv2_bonus")
