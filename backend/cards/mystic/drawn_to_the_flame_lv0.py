"""Drawn to the Flame (Level 0) — Mystic Event. (01064)
抽取遭遇牌堆顶的1张牌。然后，在你所在地点发现2条线索。

简化说明：
- 遭遇牌抽取走 ENCOUNTER_CARD_DRAWN 事件流程（与神话阶段一致，先抽后发现线索）；
  牌面揭示效果由会话/剧本层消费该事件结算（当前会话层仅在神话流程中结算
  遭遇牌揭示，调查阶段抽到的牌只入遭遇弃牌堆——遗留简化）。
- 实现需要在事件总线上再发射 ENCOUNTER_CARD_DRAWN，因此在 register() 时
  保存总线引用（EventBus 支持嵌套 emit）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class DrawnToTheFlame(CardImplementation):
    card_id = "drawn_to_the_flame_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def discover_clues(self, ctx):
        """先抽遭遇牌堆顶1张，然后在所在地点发现2条线索。"""
        if ctx.extra.get("card_id") != "drawn_to_the_flame_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # 1) 抽取遭遇牌堆顶牌（走 ENCOUNTER_CARD_DRAWN 流程）
        scenario = ctx.game_state.scenario
        if scenario.encounter_deck:
            card_id = scenario.encounter_deck.pop(0)
            scenario.encounter_discard.append(card_id)
            ctx.extra["drawn_to_the_flame_encounter"] = card_id
            if self._bus is not None:
                from backend.engine.event_bus import EventContext
                self._bus.emit(EventContext(
                    game_state=ctx.game_state,
                    event=GameEvent.ENCOUNTER_CARD_DRAWN,
                    investigator_id=ctx.investigator_id,
                    extra={"card_id": card_id},
                ))
            ctx.game_state.log_effect(
                f"🔥 飞蛾扑火：抽取遭遇牌【{ctx.game_state.card_name(card_id)}】")

        # 2) 在所在地点发现2条线索
        location = ctx.game_state.get_location(inv.location_id)
        if location:
            clues = min(2, location.clues)
            location.clues -= clues
            inv.clues += clues
