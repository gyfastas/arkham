"""Last Chance (Level 0) — Survivor Skill. (04036)
Commit only to a skill test with no other cards committed to it. Other
cards cannot be committed to this skill test.
Last Chance loses [wild] for each card in your hand.

简化说明：
- 5 个万能图标为数据静态值；本实现按手牌张数扣减（投入时投入卡仍在
  手牌中，故孤注一掷自身也计入手牌数），下限0（不扣成负数）。
- "只能投给无其他投入卡的检定，且其他卡不能再投入"为投入限制，需
  会话层/UI 支持，本实现不强制（引擎缺口，见报告）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_PRINTED_WILD = 5


class LastChance(CardImplementation):
    card_id = "last_chance_lv0"

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def scale_with_hand(self, ctx):
        """手牌每张 -1 万能图标（下限0）。"""
        if self.card_id not in (ctx.committed_cards or []):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        effective = max(0, _PRINTED_WILD - len(inv.hand))
        delta = effective - _PRINTED_WILD
        if delta:
            ctx.modify_amount(delta, "last_chance_hand_size")
            ctx.extra["last_chance_icons"] = effective
