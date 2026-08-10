"""Extensive Research (Level 1) — Seeker Event. (06198)
你每有1张其它手牌，降低海量研究的打出费用1点。
发现你所在地点的2个线索。

简化说明：
- 引擎出牌流程直接读取 card_data.cost（无动态费用钩子，引擎缺口），
  故费用减免实现为"打出后返还"：返还 = min(打出后手牌数, 10)——打出后
  的手牌即官方的"其它手牌"，净支出与官方一致；但资源不足全额10点时
  无法打出（引擎缺口，见报告）；
- 线索发现发 CLUE_DISCOVERED（一次，amount=实际发现数），与引擎调查行动一致。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_FULL_COST = 10


class ExtensiveResearch(CardImplementation):
    card_id = "extensive_research_lv1"

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def discover_and_refund(self, ctx):
        if ctx.extra.get("card_id") != "extensive_research_lv1":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # 费用减免（返还）：每张其它手牌减1
        refund = min(len(inv.hand), _FULL_COST)
        if refund:
            inv.resources += refund
            ctx.extra["extensive_research_refund"] = refund

        # 发现你所在地点的2个线索
        location = ctx.game_state.get_location(inv.location_id)
        if location is None:
            return
        found = min(2, location.clues)
        if found <= 0:
            return
        location.clues -= found
        inv.clues += found
        ctx.extra["extensive_research_clues"] = found
        ctx.game_state.log_effect(f"🔬 海量研究：发现{found}个线索")
        bus = getattr(self, "_bus", None)
        if bus is not None:
            from backend.engine.event_bus import EventContext
            bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.CLUE_DISCOVERED,
                investigator_id=inv.investigator_id,
                location_id=inv.location_id,
                amount=found,
                source=self.instance_id,
            ))
