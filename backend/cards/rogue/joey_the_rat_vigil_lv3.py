"""Joey "The Rat" Vigil (Level 3) — Rogue Asset, Ally slot. (06326)
[快速]花费1资源：选择你手牌中的一张[[物品]]支援卡并打出（支付其费用）。
[快速]弃置一张在场的[[物品]]支援卡：获得2资源。

简化说明：
- 两个能力均为公开方法（play_item / pawn_item），目标由 UI/会话层选择。
- play_item 直接构建在场实例（同 calling_in_favors）：支付1资源+物品费用，
  占用槽位并发射 CARD_ENTERS_PLAY；其卡牌能力的注册/激活需会话层接线
  （卡牌 handler 无法访问 CardRegistry，引擎缺口，同 calling_in_favors）。
- pawn_item 可弃置任意你控制的在场[[物品]]支援（含本卡以外的）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority
from backend.models.state import CardInstance


def _is_item_asset(game_state, card_id) -> bool:
    cd = game_state.get_card_data(card_id)
    return (cd is not None and cd.type == CardType.ASSET
            and "item" in (cd.traits or []))


class JoeyTheRatVigil(CardImplementation):
    card_id = "joey_the_rat_vigil_lv3"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def play_item(self, game_state, investigator_id: str, card_id: str) -> bool:
        """[快速]花费1资源：从手牌打出一张[[物品]]支援卡（支付其费用）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        if card_id not in inv.hand or not _is_item_asset(game_state, card_id):
            return False
        cd = game_state.get_card_data(card_id)
        cost = cd.cost or 0
        if inv.resources < 1 + cost:
            return False
        inv.resources -= 1 + cost
        inv.hand.remove(card_id)

        inst_id = game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id=card_id,
            owner_id=inv.investigator_id,
            controller_id=inv.investigator_id,
            slot_used=list(cd.slots or []),
        )
        if cd.uses:
            ci.uses = dict(cd.uses)
        game_state.cards_in_play[inst_id] = ci
        inv.play_area.append(inst_id)
        slot_mgr = getattr(game_state, "slot_managers", {}).get(investigator_id)
        if slot_mgr is not None and cd.slots:
            slot_mgr.occupy(inst_id, cd.slots, cd.traits)

        from backend.engine.event_bus import EventContext
        if self._bus is not None:
            self._bus.emit(EventContext(
                game_state=game_state,
                event=GameEvent.CARD_ENTERS_PLAY,
                investigator_id=investigator_id,
                target=inst_id,
                extra={"card_id": card_id},
            ))
        game_state.log_effect(
            f"🐀 老鼠乔伊：快速打出【{game_state.card_name(card_id)}】")
        return True

    def pawn_item(self, game_state, investigator_id: str,
                  instance_id: str) -> bool:
        """[快速]弃置一张你控制的在场[[物品]]支援卡：获得2资源。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        if instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(instance_id)
        if inst is None or not _is_item_asset(game_state, inst.card_id):
            return False

        slot_mgr = getattr(game_state, "slot_managers", {}).get(investigator_id)
        if slot_mgr is not None:
            slot_mgr.vacate(instance_id)
        inv.play_area.remove(instance_id)
        inv.discard.append(inst.card_id)
        game_state.cards_in_play.pop(instance_id, None)
        inv.resources += 2

        from backend.engine.event_bus import EventContext
        if self._bus is not None:
            self._bus.emit(EventContext(
                game_state=game_state,
                event=GameEvent.CARD_LEAVES_PLAY,
                investigator_id=investigator_id,
                target=instance_id,
                extra={"card_id": inst.card_id},
            ))
        game_state.log_effect(
            f"🐀 老鼠乔伊：典押【{game_state.card_name(inst.card_id)}】，获得2资源")
        return True
