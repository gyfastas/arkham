"""Tempt Fate (Level 0) — Neutral Event. (07037)
快速。在任意[fast]窗口打出。
向混沌袋中加入3个[诅咒]标记。然后，向混沌袋中加入3个[祝福]标记并抽1张牌。

简化说明：
- 混沌袋经 bind_chaos_bag() 注入（registry.activate_card 自动绑定）；
  未绑定时只抽牌不加标记。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class TemptFate(CardImplementation):
    card_id = "tempt_fate_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入混沌袋（registry 自动绑定）。"""
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.AFTER)
    def resolve(self, ctx):
        if ctx.extra.get("card_id") != "tempt_fate_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if self._chaos_bag is not None:
            for _ in range(3):
                self._chaos_bag.add_token(ChaosTokenType.CURSE)
            for _ in range(3):
                self._chaos_bag.add_token(ChaosTokenType.BLESS)
        if inv.deck:
            inv.hand.append(inv.deck.pop(0))
        ctx.extra["tempt_fate_resolved"] = True
