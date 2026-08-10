"""Untimely Transaction (Level 1) — Rogue Event. (08051)
揭示你手中的一张[[道具]]支援卡。你所在地点的另一位调查员可以打出该支援卡，
如同其在他的手牌中。如果他这么做，你抽取1张卡牌并获得等于该支援卡打印
费用的资源。

简化说明：
- 道具与目标调查员自动选择：手中第一张道具卡 + 你所在地点第一位付得起
  其打印费用的其他调查员；可用 ctx.extra["item_card_id"] /
  ctx.extra["target_investigator_id"] 显式指定（官方为玩家选择，
  且对方可以拒绝——简化为付得起就打）。
- 对方"如同在其手牌中打出"：对方支付打印费用，卡直接从你的手牌进入其
  装备区并发 CARD_ENTERS_PLAY；新入场支援的卡面实现注册由会话层负责
  （事件实现拿不到 registry——引擎缺口）。
- 无人可打出时（无道具/无其他调查员/无人付得起）效果落空，卡仍弃置。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority


class UntimelyTransaction(CardImplementation):
    card_id = "untimely_transaction_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus  # 入场需要经事件总线发出 CARD_ENTERS_PLAY

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def resolve(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        item_id = ctx.extra.get("item_card_id") or self._first_item(ctx, inv)
        if item_id is None or item_id not in inv.hand:
            return
        cd = ctx.game_state.get_card_data(item_id)
        if cd is None or cd.type != CardType.ASSET or "item" not in (cd.traits or []):
            return
        cost = cd.cost or 0

        target_id = ctx.extra.get("target_investigator_id")
        if target_id is None:
            target_id = self._first_buyer(ctx, inv, cost)
        target = ctx.game_state.get_investigator(target_id) if target_id else None
        if target is None or target.investigator_id == inv.investigator_id:
            return
        if target.location_id != inv.location_id or target.resources < cost:
            return

        # 对方支付费用，道具从你的手牌进入其装备区
        target.resources -= cost
        inv.hand.remove(item_id)
        from backend.models.state import CardInstance
        new_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=new_id,
            card_id=item_id,
            owner_id=target.investigator_id,
            controller_id=target.investigator_id,
            slot_used=list(cd.slots or []),
        )
        if cd.uses:
            ci.uses = dict(cd.uses)
        ctx.game_state.cards_in_play[new_id] = ci
        target.play_area.append(new_id)
        if self._bus is not None:
            from backend.engine.event_bus import EventContext
            self._bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.CARD_ENTERS_PLAY,
                investigator_id=target.investigator_id,
                target=new_id,
                extra={"card_id": item_id},
            ))

        # 你抽1张牌并获得等于打印费用的资源
        if inv.deck:
            inv.hand.append(inv.deck.pop(0))
        inv.resources += cost

        ctx.extra["untimely_transaction_item"] = item_id
        ctx.extra["untimely_transaction_buyer"] = target.investigator_id
        ctx.extra["untimely_transaction_refund"] = cost
        ctx.game_state.log_effect(
            f"🤝 不合时宜的交易：{ctx.game_state.card_name(item_id)}由队友打出，"
            f"你抽1张牌并获得{cost}资源")

    @staticmethod
    def _first_item(ctx, inv) -> str | None:
        for cid in inv.hand:
            cd = ctx.game_state.get_card_data(cid)
            if (
                cd is not None
                and cd.type == CardType.ASSET
                and "item" in (cd.traits or [])
            ):
                return cid
        return None

    @staticmethod
    def _first_buyer(ctx, inv, cost: int) -> str | None:
        for other in ctx.game_state.get_investigators_at_location(inv.location_id):
            if other.investigator_id == inv.investigator_id:
                continue
            if other.resources >= cost:
                return other.investigator_id
        return None
