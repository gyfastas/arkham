"""Empty Vessel (Level 4) — Guardian Asset, Accessory slot. (06276)
每套牌限制1张。使用(0充能)。
[反应]在你击败一名敌人后：在空虚项链上放置1个充能。
[快速]如果空虚项链上有至少3个充能：在你的绑定卡牌中查找食愿项链，
并将它与空虚项链交换，将空虚项链上的所有充能移到食愿项链上。

简化说明：
- 击败敌人放置充能：ENEMY_DEFEATED（ctx.investigator_id 为击败者）触发。
- 绑定交换：绑定卡不在任何游戏区域（游戏外），交换实现为空虚项链移出游戏
  （scenario.vars["out_of_play"]，同 miss_doyle 惯例）、食愿项链带充能入场
  并占用饰品槽。⚠️ 食愿项链自身的实现注册需会话层接线（引擎缺口，
  同 miss_doyle/a_chance_encounter 惯例）。
- 数据 uses 键兼容 "charges"/"chargess"（抓取复数化瑕疵）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, SlotType, TimingPriority
from backend.models.state import CardInstance

WISH_EATER = "wish_eater_lv0"
_SWAP_COST = 3


class EmptyVessel(CardImplementation):
    card_id = "empty_vessel_lv4"
    activations = [{
        "id": "swap",
        "label": "≥3充能：与绑定卡食愿项链交换",
        "method": "activate_swap",
        "actions": 0,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @staticmethod
    def _key(inst) -> str:
        if "charges" in inst.uses:
            return "charges"
        return "chargess" if "chargess" in inst.uses else "charges"

    @on_event(GameEvent.ENEMY_DEFEATED, priority=TimingPriority.AFTER)
    def gain_charge(self, ctx):
        """你击败敌人后：放置1个充能。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return
        key = self._key(inst)
        inst.uses[key] = inst.uses.get(key, 0) + 1
        ctx.extra["empty_vessel_charges"] = inst.uses[key]
        ctx.game_state.log_effect(
            f"🫙 空虚项链：击败敌人，充能+1（现有{inst.uses[key]}）")

    def activate_swap(self, game_state, investigator_id: str) -> bool:
        """≥3充能：与绑定的食愿项链交换，充能全部转移。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        key = self._key(inst)
        charges = inst.uses.get(key, 0)
        if charges < _SWAP_COST:
            return False
        wish_data = game_state.get_card_data(WISH_EATER)
        if wish_data is None:
            return False

        # 空虚项链移出游戏（绑定区），食愿项链带充能入场
        inv.play_area.remove(self.instance_id)
        game_state.cards_in_play.pop(self.instance_id, None)
        slot_mgr = getattr(game_state, "slot_managers", {}).get(investigator_id)
        if slot_mgr is not None:
            slot_mgr.vacate(self.instance_id)
        if self._bus is not None:
            self._bus.unregister_card(self.instance_id)
        game_state.scenario.vars.setdefault("out_of_play", []).append(self.card_id)

        new_id = game_state.next_instance_id()
        wish = CardInstance(
            instance_id=new_id,
            card_id=WISH_EATER,
            owner_id=investigator_id,
            controller_id=investigator_id,
            slot_used=[SlotType.ACCESSORY],
            uses={"charges": charges},
        )
        game_state.cards_in_play[new_id] = wish
        inv.play_area.append(new_id)
        if slot_mgr is not None:
            slot_mgr.occupy(new_id, [SlotType.ACCESSORY], wish_data.traits)
        game_state.log_effect(
            f"🫙 空虚项链：与食愿项链交换，转移{charges}个充能")
        return True
