"""Harmony Restored (Level 2) — Survivor Event. (07712 批次)
Search the chaos bag for X [curse] tokens and return them to the token pool.
X is the number of [bless] tokens in the chaos bag. Gain 1 resource for each
[curse] token removed in this way.

简化说明：
- 混沌袋经 bind_chaos_bag() 注入（registry.activate_card 自动接线）；
  未绑定时效果落空。
- "返回标记池"即从袋中移除（引擎无独立标记池状态）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class HarmonyRestored(CardImplementation):
    card_id = "harmony_restored_lv2"

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def purge_curses(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        bag = getattr(self, "_chaos_bag", None)
        if inv is None or bag is None:
            return

        x = sum(1 for t in bag.tokens if t == ChaosTokenType.BLESS)
        removed = 0
        for _ in range(x):
            if bag.remove(ChaosTokenType.CURSE):
                removed += 1
            else:
                break
        inv.resources += removed
        ctx.extra["harmony_restored_removed"] = removed
        ctx.game_state.log_effect(
            f"☯️ 恢复和谐：从混沌袋移除{removed}个诅咒标记，获得{removed}资源")
