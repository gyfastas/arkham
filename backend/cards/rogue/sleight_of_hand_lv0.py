"""Sleight of Hand (Level 0) — Rogue Event.
快速。只能在你回合中打出。将手牌中的一张[[道具]]支援卡放置入场。
当你回合结束时，如果该支援卡还在场上，将其收回你的手牌。

简化说明：
- 目标道具默认选择手牌中第一张道具支援卡，可用 ctx.extra["asset_card_id"]
  指定（官方为玩家自选）。
- 放置入场不支付费用（官方效果）；占槽直接登记（槽位冲突校验由会话层负责）。
- 被放入资产的卡牌实现注册需要 registry 引用（卡实现拿不到），
  引擎缺口：放入场的资产其 on_event 能力本回合不生效。
- "只能在你回合中打出"的时机校验由会话层负责。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority
from backend.models.state import CardInstance


class SleightOfHand(CardImplementation):
    card_id = "sleight_of_hand_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._loaned_instance_id: str | None = None
        self._owner_id: str | None = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus  # 放置入场需要经事件总线发出 CARD_ENTERS_PLAY

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def put_item_into_play(self, ctx):
        if ctx.extra.get("card_id") != "sleight_of_hand_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        def _is_item_asset(card_id: str) -> bool:
            cd = ctx.game_state.get_card_data(card_id)
            return (
                cd is not None
                and cd.type == CardType.ASSET
                and "item" in (cd.traits or [])
            )

        asset_id = ctx.extra.get("asset_card_id")
        if asset_id is not None:
            if asset_id not in inv.hand or not _is_item_asset(asset_id):
                return
        else:
            asset_id = next((cid for cid in inv.hand if _is_item_asset(cid)), None)
            if asset_id is None:
                return

        card_data = ctx.game_state.get_card_data(asset_id)
        inv.hand.remove(asset_id)

        instance_id = ctx.game_state.next_instance_id()
        inst = CardInstance(
            instance_id=instance_id,
            card_id=asset_id,
            owner_id=inv.investigator_id,
            controller_id=inv.investigator_id,
            slot_used=list(card_data.slots or []),
        )
        if card_data.uses:
            inst.uses = dict(card_data.uses)
        ctx.game_state.cards_in_play[instance_id] = inst
        inv.play_area.append(instance_id)
        slot_mgr = getattr(ctx.game_state, "slot_managers", {}).get(inv.investigator_id)
        if slot_mgr is not None and card_data.slots:
            slot_mgr.occupy(instance_id, card_data.slots, card_data.traits)

        self._loaned_instance_id = instance_id
        self._owner_id = inv.investigator_id

        ctx.extra["sleight_of_hand_instance"] = instance_id
        ctx.game_state.log_effect(f"🖐️ 巧手：{ctx.game_state.card_name(asset_id)}临时入场")
        if self._bus is not None:
            from backend.engine.event_bus import EventContext
            self._bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.CARD_ENTERS_PLAY,
                investigator_id=inv.investigator_id,
                target=instance_id,
                extra={"card_id": asset_id},
            ))

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def stop_tracking(self, ctx):
        """道具中途离场（被弃/被击败）：不再追踪。"""
        if ctx.target == self._loaned_instance_id:
            self._loaned_instance_id = None
            self._owner_id = None

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def return_to_hand(self, ctx):
        """你的回合结束时：道具仍在场则收回手牌。"""
        if self._loaned_instance_id is None:
            return
        if ctx.investigator_id != self._owner_id:
            return
        inv = ctx.game_state.get_investigator(self._owner_id)
        inst = ctx.game_state.get_card_instance(self._loaned_instance_id)
        iid = self._loaned_instance_id
        self._loaned_instance_id = None
        self._owner_id = None
        if inv is None or inst is None or iid not in inv.play_area:
            return
        slot_mgr = getattr(ctx.game_state, "slot_managers", {}).get(inv.investigator_id)
        if slot_mgr is not None:
            slot_mgr.vacate(iid)
        inv.play_area.remove(iid)
        ctx.game_state.cards_in_play.pop(iid, None)
        inv.hand.append(inst.card_id)
        ctx.extra["sleight_of_hand_returned"] = inst.card_id
        ctx.game_state.log_effect(
            f"🖐️ 巧手：{ctx.game_state.card_name(inst.card_id)}收回手牌")
