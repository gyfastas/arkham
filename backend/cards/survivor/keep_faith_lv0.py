"""Keep Faith (Level 0) — Survivor Event. (05237 批次)
Fast. Play during any [fast] window.
Add 4 [bless] tokens to the chaos bag.

简化说明：
- 混沌袋经 bind_chaos_bag() 注入（registry.activate_card 自动接线）；
  未绑定时效果落空。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class KeepFaith(CardImplementation):
    card_id = "keep_faith_lv0"

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def add_bless_tokens(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        bag = getattr(self, "_chaos_bag", None)
        if bag is None:
            return
        for _ in range(4):
            bag.add_token(ChaosTokenType.BLESS)
        ctx.extra["keep_faith_blessed"] = 4
        ctx.game_state.log_effect("🙏 坚守信念：向混沌袋加入4个祝福标记")
