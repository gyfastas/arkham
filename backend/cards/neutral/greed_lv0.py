"""Greed — Neutral Treachery, Weakness.
显现 - 受到1点恐惧。若你的资源…
- …不超过10，额外受到1点恐惧。
- …不超过5，额外受到1点恐惧。
- …为0，额外受到1点恐惧。

简化说明：
- 恐惧经 DamageEngine 结算（可被支援卡承伤，符合官方规则）；
  事件总线在 register() 时保存。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Greed(CardImplementation):
    card_id = "greed_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "greed_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        horror = 1
        if inv.resources <= 10:
            horror += 1
        if inv.resources <= 5:
            horror += 1
        if inv.resources <= 0:
            horror += 1

        if "greed_lv0" in inv.hand:
            inv.hand.remove("greed_lv0")
        inv.discard.append("greed_lv0")

        from backend.engine.damage import DamageEngine
        DamageEngine(ctx.game_state, self._bus).deal_damage(
            ctx.investigator_id, horror=horror,
        )
        ctx.game_state.log_effect(f"💰 贪婪：受到 {horror} 点恐惧")
