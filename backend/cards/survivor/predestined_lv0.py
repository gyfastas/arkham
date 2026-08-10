"""Predestined (Level 0) — Survivor Skill. (07035)
Max 1 committed per skill test.
You may commit Predestined to any type of test.
If this test fails, either add 2 [bless] tokens to the chaos bag or remove
2 [curse] tokens from the chaos bag.

简化说明：
- 效果自动选择：袋中有诅咒标记时移除至多2个诅咒，否则加入2个祝福
  （官方为玩家二选一）。
- "可投入任何类型检定""每次检定限1张"为投入限制，需会话层/UI 支持，
  本实现不强制（引擎缺口，见报告）。
- 混沌袋经 bind_chaos_bag() 注入（投入激活时 registry 自动接线）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class Predestined(CardImplementation):
    card_id = "predestined_lv0"

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.AFTER)
    def bless_or_purge(self, ctx):
        """本次检定失败：移除至多2个诅咒，或加入2个祝福。"""
        if self.card_id not in (ctx.committed_cards or []):
            return
        bag = getattr(self, "_chaos_bag", None)
        if bag is None:
            return
        removed = 0
        for _ in range(2):
            if bag.remove(ChaosTokenType.CURSE):
                removed += 1
            else:
                break
        if removed:
            ctx.extra["predestined_curses_removed"] = removed
            ctx.game_state.log_effect(
                f"🔮 命中注定：检定失败，从混沌袋移除{removed}个诅咒标记")
        else:
            for _ in range(2):
                bag.add_token(ChaosTokenType.BLESS)
            ctx.extra["predestined_blessed"] = 2
            ctx.game_state.log_effect(
                "🔮 命中注定：检定失败，向混沌袋加入2个祝福标记")
