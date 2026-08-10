"""Wish Eater (Level 0) — Guardian Asset, Accessory slot. (06277)
绑定(空虚项链)。
[反应]你在技能检定中抽出一个[骷髅]/[邪教徒]/[石板]/[远古之物]混乱标记时，
花费1充能：取消该标记。治愈1点伤害和1点恐惧。
强制 - 如果食愿项链没有充能：在你的绑定卡牌中查找空虚项链，并将其与
食愿项链交换。

简化说明：
- 取消为自动触发（有充能且揭示上述标记时自动花费，官方为玩家选择；
  与 grotesque_statue_lv4 的自动选择简化一致）。
- 取消的结算：在 CHAOS_TOKEN_RESOLVED 把标记修正清零。剧本符号标记的
  数值修正可被抵消；但剧本 handler 在 WHEN 阶段先注册先执行，其附加
  效果（"若失败则…"等挂起标记）无法撤回（引擎无通用"标记已取消"通道，
  缺口见报告）。
- 绑定卡堆未建模：强制交换以 empty_vessel_lv4 数据在场内创建实例
  （继承 accessory 槽与剩余充能——触发时没有充能，即为0），食愿项链
  移出游戏（回绑定堆，不进弃牌堆）；empty_vessel_lv4 数据未注册时
  退化为仅记日志。
- 反向交换（空虚项链→食愿项链并移充能）属空虚项链卡面效果，不在本卡。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import (
    ChaosTokenType, GameEvent, SlotType, TimingPriority,
)
from backend.models.state import CardInstance

_BAD_TOKENS = {
    ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING,
}
_EMPTY_VESSEL = "empty_vessel_lv4"


class WishEater(CardImplementation):
    card_id = "wish_eater_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def cancel_token(self, ctx):
        """揭示 skull/cultist/tablet/elder_thing 时自动花1充能：取消并治愈。"""
        if ctx.chaos_token not in _BAD_TOKENS:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("charges", 0) <= 0:
            return

        inst.uses["charges"] -= 1
        # 取消标记：修正清零（对剧本数值修正同样生效，见 docstring 缺口）
        if ctx.amount:
            ctx.modify_amount(-ctx.amount, "wish_eater_cancel")
        ctx.extra["wish_eater_cancelled"] = getattr(
            ctx.chaos_token, "value", str(ctx.chaos_token))

        # 治愈1点伤害和1点恐惧
        healed_damage = min(1, inv.damage)
        healed_horror = min(1, inv.horror)
        inv.damage -= healed_damage
        inv.horror -= healed_horror
        ctx.game_state.log_effect(
            "📿 食愿项链：花费1充能，取消"
            f"【{ctx.extra['wish_eater_cancelled']}】标记，治愈1伤害1恐惧")

        if inst.uses.get("charges", 0) <= 0:
            self._swap_to_empty_vessel(ctx.game_state, inv)

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def forced_swap_on_enter(self, ctx):
        """强制 - 没有充能时（含直接打出0充能的情况）：交换为空虚项链。"""
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None:
            return
        if inst.uses.get("charges", 0) <= 0:
            self._swap_to_empty_vessel(ctx.game_state, inv)

    def _swap_to_empty_vessel(self, game_state, inv) -> None:
        """强制交换：食愿项链回绑定堆，空虚项链带剩余充能入场（同槽位）。"""
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        if game_state.get_card_data(_EMPTY_VESSEL) is None:
            game_state.log_effect(
                "📿 食愿项链：充能耗尽应交换为空虚项链，但其数据未注册，保持原位")
            return
        charges = inst.uses.get("charges", 0)

        # 食愿项链离场（回绑定堆，不进弃牌堆）
        vacate_asset_slots(game_state, self.instance_id)
        if self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
        game_state.cards_in_play.pop(self.instance_id, None)
        if self._bus is not None:
            self.unregister(self._bus)

        # 空虚项链入场（继承 accessory 槽与充能）
        new_iid = game_state.next_instance_id()
        vessel = CardInstance(
            instance_id=new_iid,
            card_id=_EMPTY_VESSEL,
            owner_id=inv.investigator_id,
            controller_id=inv.investigator_id,
            slot_used=[SlotType.ACCESSORY],
        )
        vessel.uses["charges"] = charges
        game_state.cards_in_play[new_iid] = vessel
        inv.play_area.append(new_iid)
        slot_mgr = getattr(game_state, "slot_managers", {}).get(
            inv.investigator_id)
        if slot_mgr is not None:
            cd = game_state.get_card_data(_EMPTY_VESSEL)
            slot_mgr.occupy(new_iid, [SlotType.ACCESSORY],
                            getattr(cd, "traits", []) or [])
        game_state.log_effect("📿 食愿项链：充能耗尽，交换为空虚项链")
