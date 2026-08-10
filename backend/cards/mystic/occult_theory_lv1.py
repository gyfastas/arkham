"""Occult Theory (Level 1) — Mystic Skill.
当奥秘理论在你手牌中或被投入技能检定时，它获得数量等同于你[intellect]的
[willpower]图标，以及数量等同于你[willpower]的[intellect]图标。

简化说明：
- 动态图标在 SKILL_TEST_COMMIT 结算：意志检定加入等量智力值图标、
  智力检定加入等量意志值图标；其他技能检定无匹配图标（无[wild]）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class OccultTheory(CardImplementation):
    card_id = "occult_theory_lv1"

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def dynamic_icons(self, ctx):
        if self.card_id not in (ctx.committed_cards or []):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if ctx.skill_type == Skill.WILLPOWER:
            bonus = inv.get_skill(Skill.INTELLECT)
        elif ctx.skill_type == Skill.INTELLECT:
            bonus = inv.get_skill(Skill.WILLPOWER)
        else:
            return
        if bonus > 0:
            ctx.modify_amount(bonus, f"{self.card_id}_icons")
            ctx.extra[f"{self.card_id}_bonus_icons"] = bonus
