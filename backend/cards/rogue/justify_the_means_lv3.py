"""Justify the Means (Level 3) — Rogue Skill. (07306)
你可以将为达目的投入任意类型的检定。
作为将为达目的投入技能检定的额外费用，向混沌袋加入等同于本次检定难度
数量的[curse]标记。
本次检定自动成功。

简化说明：
- "投入任意类型的检定"由会话层的投入校验执行（引擎不校验投入合法性，
  引擎缺口）。
- 额外费用在 SKILL_TEST_COMMIT 时支付：[curse]按官方规则袋中上限10个
  封顶（同 promise_of_power）；混沌袋经 bind_chaos_bag() 注入。
- 自动成功经 SKILL_TEST_FAILED 翻转 ctx.success（同 lucky 通道）；
  即便揭示[auto_fail]仍成功（官方裁定自动成功优先，列为简化说明）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

_MAX_CURSE_TOKENS = 10


class JustifyTheMeans(CardImplementation):
    card_id = "justify_the_means_lv3"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None
        self._armed = False

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def pay_curses(self, ctx):
        """投入的额外费用：加入等同于检定难度数量的[curse]标记。"""
        if "justify_the_means_lv3" not in ctx.committed_cards:
            return
        difficulty = ctx.difficulty or 0
        added = 0
        if self._chaos_bag is not None and difficulty > 0:
            existing = sum(1 for t in self._chaos_bag.tokens + self._chaos_bag.sealed
                           if t == ChaosTokenType.CURSE)
            for _ in range(min(difficulty, max(0, _MAX_CURSE_TOKENS - existing))):
                self._chaos_bag.add_token(ChaosTokenType.CURSE)
                added += 1
        self._armed = True
        ctx.extra["justify_the_means_curses"] = added
        ctx.game_state.log_effect(
            f"⚖ 为达目的：混沌袋加入{added}个[curse]，本次检定自动成功")

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.WHEN)
    def auto_success(self, ctx):
        if not self._armed:
            return
        ctx.success = True
        ctx.extra["justify_the_means_auto_success"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
