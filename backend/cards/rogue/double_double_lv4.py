"""Double, Double (Level 4) — Rogue Asset, Arcane slot. (05320)
卓越。
[反应]在你打出一张事件卡后，消耗超级加倍：再次打出该事件卡，如同其在你
手牌中。

简化说明：
- 自动触发（官方为玩家选择时机）：你打出事件后若本卡未横置且你付得起
  该事件的费用，自动消耗本卡并再结算一次该事件（重新支付费用——"如同在
  手牌中打出"包含支付费用）。
- 二次打出通过再次发出 CARD_PLAYED（带 double_double_replay 标记）实现，
  本卡对带该标记的打出不再响应，避免递归。
- "卓越"（每牌组限1）为牌组构建规则，由会话层负责。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority


class DoubleDouble(CardImplementation):
    card_id = "double_double_lv4"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.REACTION)
    def replay_event(self, ctx):
        """你打出一张事件后：消耗本卡，重新支付费用并再结算一次。"""
        card_id = ctx.extra.get("card_id")
        if not card_id or ctx.extra.get("double_double_replay"):
            return
        cd = ctx.game_state.get_card_data(card_id)
        if cd is None or cd.type != CardType.EVENT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted or self._bus is None:
            return
        cost = cd.cost or 0
        if inv.resources < cost:
            return

        inv.resources -= cost
        inst.exhausted = True
        ctx.extra["double_double_replayed"] = card_id
        ctx.game_state.log_effect(
            f"🔁 超级加倍：消耗并支付{cost}资源，再次结算【{ctx.game_state.card_name(card_id)}】")

        from backend.engine.event_bus import EventContext
        self._bus.emit(EventContext(
            game_state=ctx.game_state,
            event=GameEvent.CARD_PLAYED,
            investigator_id=ctx.investigator_id,
            source=ctx.source,
            extra={"card_id": card_id, "double_double_replay": True},
        ))
