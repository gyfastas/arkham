"""Steadfast (Level 0) — Guardian Skill. (05022)
印刷图标：[willpower][combat]。
只要你剩余生命值和神智值总合至少为5时，坚定不移获得[willpower][combat]
(总合至少为10时，改为获得[willpower][willpower][combat][combat])。

实现说明：
- 印刷的1意志1战斗图标由引擎按 skill_icons 自动计入；本实现追加条件图标：
  剩余生命+神智≥5 追加1（意志或战斗检定时），≥10 追加2。
- 条件图标仅对意志/战斗检定生效（卡面图标本就不适用于其他技能）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Steadfast(CardImplementation):
    card_id = "steadfast_lv0"

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def conditional_icons(self, ctx):
        """按剩余生命+神智追加条件图标（≥5:+1，≥10:+2）。"""
        if self.card_id not in (ctx.committed_cards or []):
            return
        if ctx.skill_type not in (Skill.WILLPOWER, Skill.COMBAT):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        remaining = inv.remaining_health + inv.remaining_sanity
        if remaining >= 10:
            bonus = 2
        elif remaining >= 5:
            bonus = 1
        else:
            return
        ctx.modify_amount(bonus, "steadfast_conditional_icons")
