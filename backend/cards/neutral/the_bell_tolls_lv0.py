"""The Bell Tolls (Level 0) — Neutral Treachery, Weakness. (04042)
显现 - 你的死期已到。你被**杀死**。

简化说明：
- "被杀死"实现为直接致命伤害（damage = 生命值上限）并发射
  INVESTIGATOR_DEFEATED（extra["killed"]=True，供战役层区分"杀死"与
  "击败"：杀死承受1点肉体创伤）。本卡随后进入弃牌堆。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class TheBellTolls(CardImplementation):
    card_id = "the_bell_tolls_lv0"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "the_bell_tolls_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "the_bell_tolls_lv0" in inv.hand:
            inv.hand.remove("the_bell_tolls_lv0")

        inv.damage = inv.health  # 被杀死：直接致命
        inv.discard.append("the_bell_tolls_lv0")
        ctx.extra["the_bell_tolls_killed"] = True

        from backend.engine.event_bus import EventContext
        bus = getattr(self, "_bus", None)
        if bus is not None:
            bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.INVESTIGATOR_DEFEATED,
                investigator_id=ctx.investigator_id,
                extra={"killed": True},
            ))

    def register(self, bus, instance_id: str) -> None:
        self._bus = bus
        super().register(bus, instance_id)
