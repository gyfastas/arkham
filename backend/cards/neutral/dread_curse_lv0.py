"""Dread Curse (Level 0) — Neutral Treachery, Basic Weakness.
显现：向混沌袋中加入5个[curse]标记。

简化说明：
- 混沌袋通过 bind_chaos_bag() 注入（与 rexs_curse_lv0 同一惯例；
  会话层经 emit_card_drawn(chaos_bag=...) 自动绑定）。未绑定时不加标记。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class DreadCurse(CardImplementation):
    card_id = "dread_curse_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "dread_curse_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "dread_curse_lv0" in inv.hand:
            inv.hand.remove("dread_curse_lv0")

        if self._chaos_bag is not None:
            for _ in range(5):
                self._chaos_bag.add_token(ChaosTokenType.CURSE)
            ctx.extra["dread_curse_added"] = 5
            ctx.game_state.log_effect("🌑 恐怖诅咒：混沌袋加入5个[curse]标记")

        inv.discard.append("dread_curse_lv0")
