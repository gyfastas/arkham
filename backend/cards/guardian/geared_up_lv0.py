"""Geared Up (Level 0) — Guardian Asset (Permanent). (08019)
永久。每卡组限1张。构筑牌组时购买。
强制 - 当你的游戏第一个回合开始时：逐一从手牌打出任意数量的[[物品]]支援卡，
每张费用-1。本回合你少3点行动。

简化说明：
- "永久/构筑时购买"为牌组构筑规则，由会话/构筑层处理（开局即在场）。
- "任意数量"自动选择：按手牌顺序打出所有（减费后）付得起的物品支援卡；
  官方为玩家逐张选择（可经 set_pending() 传入候选列表限制，见下）。
- 新入场支援卡的实现注册需会话层接线（同 miss_doyle 缺口）；
  占槽/费用/入场事件在本卡内结算。
- "少3点行动"：回合开始时 actions_remaining 已被引擎重置为3，
  本卡将其减至0（下限0）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority
from backend.models.state import CardInstance


class GearedUp(CardImplementation):
    card_id = "geared_up_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._done = False

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.FORCED)
    def first_turn_setup(self, ctx):
        """游戏第一个回合开始时：减费打出手牌中的物品支援，本回合-3行动。"""
        if self._done:
            return
        if ctx.game_state.scenario.round_number > 1:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        self._done = True

        played = []
        for card_id in list(inv.hand):
            data = ctx.game_state.get_card_data(card_id)
            if data is None or data.type != CardType.ASSET:
                continue
            if "item" not in (data.traits or []):
                continue
            cost = max(0, (data.cost or 0) - 1)
            if inv.resources < cost:
                continue
            slot_mgr = getattr(ctx.game_state, "slot_managers", {}).get(
                inv.investigator_id)
            if slot_mgr and data.slots and not slot_mgr.can_play_card(
                    data.slots, data.traits):
                continue  # 槽位不足：跳过该卡（简化，不提示弃置腾空）

            inv.resources -= cost
            inv.hand.remove(card_id)
            instance_id = ctx.game_state.next_instance_id()
            inst = CardInstance(
                instance_id=instance_id,
                card_id=card_id,
                owner_id=inv.investigator_id,
                controller_id=inv.investigator_id,
                slot_used=list(data.slots or []),
            )
            if data.uses:
                inst.uses = dict(data.uses)
            if slot_mgr and data.slots:
                slot_mgr.occupy(instance_id, data.slots, data.traits)
            ctx.game_state.cards_in_play[instance_id] = inst
            inv.play_area.append(instance_id)
            played.append(card_id)
            if self._bus is not None:
                from backend.engine.event_bus import EventContext
                self._bus.emit(EventContext(
                    game_state=ctx.game_state,
                    event=GameEvent.CARD_ENTERS_PLAY,
                    investigator_id=inv.investigator_id,
                    target=instance_id,
                    extra={"card_id": card_id},
                ))

        inv.actions_remaining = max(0, inv.actions_remaining - 3)
        ctx.extra["geared_up_played"] = played
        if played:
            names = "、".join(ctx.game_state.card_name(c) for c in played)
            ctx.game_state.log_effect(
                f"🎒 整装待发：减费打出【{names}】，本回合-3行动")
        else:
            ctx.game_state.log_effect("🎒 整装待发：本回合-3行动")
