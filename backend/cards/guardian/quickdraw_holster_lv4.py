"""Quickdraw Holster (Level 4) — Guardian Asset, Body slot. (08089)
[fast]：选择你游戏区域中一张仅占用1个手部槽位的[[枪械]]支援卡。将其叠加到
快拔枪套，或将其与叠加的支援卡交换。叠加的支援卡不占用手部槽位。
(叠加的支援卡限制1张。)
[fast]消耗快拔枪套：执行叠加的支援卡上的一个攻击行动而无须支付其[action]费用。

简化说明：
- 两个[fast]能力均为公开方法，由会话层经 ACTIVATE_CARD 调用：
  activate_attach() 叠加/交换（空目标时自动选第一张1手枪械），
  activate_fast_fight() 消耗本卡并返回被叠加枪械的实例 id，由会话层随后
  以 fast=True 发起该枪械的战斗行动（行动费用由会话层按返回值免除）。
- 叠加的枪械经 slot_mgr.vacate 释放手部槽位；交换时旧枪械重新占用槽位。
- 缺口：枪套离场时被叠加枪械的槽位恢复/弃置规则需要引擎离场钩子支持
  （当前经 CARD_LEAVES_PLAY 尽力恢复槽位）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, SlotType, TimingPriority


class QuickdrawHolster(CardImplementation):
    card_id = "quickdraw_holster_lv4"
    activations = [
        {
            "id": "attach",
            "label": "叠加/交换1手枪械（不占手槽）",
            "method": "activate_attach",
            "actions": 0,
        },
        {
            "id": "fast_fight",
            "label": "消耗：用叠加枪械攻击（免行动费）",
            "method": "activate_fast_fight",
            "actions": 0,
        },
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._attached: str | None = None
        self._attached_slots: list = []

    def activate_attach(self, game_state, investigator_id: str,
                        firearm_instance_id: str | None = None) -> bool:
        """[fast] 叠加一张1手枪械到枪套，或与已叠加的交换。"""
        inv = game_state.get_investigator(investigator_id)
        holster = game_state.get_card_instance(self.instance_id)
        if inv is None or holster is None or self.instance_id not in inv.play_area:
            return False
        if firearm_instance_id is None:
            firearm_instance_id = self._first_one_hand_firearm(game_state, inv)
        if firearm_instance_id is None or firearm_instance_id not in inv.play_area:
            return False
        if firearm_instance_id == self._attached:
            return False
        if not self._is_one_hand_firearm(game_state, firearm_instance_id):
            return False

        slot_mgr = getattr(game_state, "slot_managers", {}).get(investigator_id)

        # 交换：已叠加的枪械重新占用手部槽位
        if self._attached is not None:
            old = game_state.get_card_instance(self._attached)
            if old is not None:
                old.attached_to = None
                if slot_mgr is not None and self._attached_slots:
                    old_data = game_state.get_card_data(old.card_id)
                    slot_mgr.occupy(
                        old.instance_id, self._attached_slots,
                        getattr(old_data, "traits", None),
                    )
            self._attached = None
            self._attached_slots = []

        # 叠加新枪械：释放其手部槽位
        firearm = game_state.get_card_instance(firearm_instance_id)
        self._attached_slots = list(firearm.slot_used or [])
        if slot_mgr is not None:
            slot_mgr.vacate(firearm_instance_id)
        firearm.attached_to = self.instance_id
        self._attached = firearm_instance_id
        game_state.log_effect(
            f"🔫 快拔枪套：叠加【{game_state.card_name(firearm.card_id)}】（不占手槽）")
        return True

    def activate_fast_fight(self, game_state, investigator_id: str) -> str | None:
        """[fast] 消耗枪套：返回被叠加枪械实例 id 供会话层发起免费攻击。"""
        inv = game_state.get_investigator(investigator_id)
        holster = game_state.get_card_instance(self.instance_id)
        if inv is None or holster is None or self.instance_id not in inv.play_area:
            return None
        if holster.exhausted or self._attached is None:
            return None
        if game_state.get_card_instance(self._attached) is None:
            return None
        holster.exhausted = True
        game_state.log_effect("🔫 快拔枪套：消耗，以叠加枪械发起攻击（免行动费）")
        return self._attached

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def restore_on_leave(self, ctx):
        """枪套离场时：尽力恢复被叠加枪械的手部槽位占用。"""
        if ctx.target != self.instance_id or self._attached is None:
            return
        firearm = ctx.game_state.get_card_instance(self._attached)
        if firearm is not None:
            firearm.attached_to = None
            slot_mgr = getattr(ctx.game_state, "slot_managers", {}).get(
                firearm.owner_id)
            if slot_mgr is not None and self._attached_slots:
                data = ctx.game_state.get_card_data(firearm.card_id)
                slot_mgr.occupy(
                    firearm.instance_id, self._attached_slots,
                    getattr(data, "traits", None),
                )
        self._attached = None
        self._attached_slots = []

    # ------------------------------------------------------------------

    @staticmethod
    def _is_one_hand_firearm(game_state, instance_id) -> bool:
        inst = game_state.get_card_instance(instance_id)
        data = game_state.get_card_data(inst.card_id) if inst else None
        if inst is None or data is None:
            return False
        if "firearm" not in (data.traits or []):
            return False
        hand_slots = [s for s in (inst.slot_used or data.slots or [])
                      if s == SlotType.HAND]
        return len(hand_slots) == 1

    @classmethod
    def _first_one_hand_firearm(cls, game_state, inv) -> str | None:
        for iid in inv.play_area:
            if cls._is_one_hand_firearm(game_state, iid):
                return iid
        return None
