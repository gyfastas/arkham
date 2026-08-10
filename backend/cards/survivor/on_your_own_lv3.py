"""On Your Own (Level 3) — Survivor Asset. (04236)
Limit 1 per investigator.
Discard On Your Own if you control an asset that takes up an ally slot.
[reaction] When you play a [survivor] event, exhaust On Your Own: Reduce
that event's cost by 2.

简化说明：
- "费用-2"实现为退款：引擎的打出流程在 CARD_PLAYED 前已全额收费，此处
  横置并返还 min(2, 事件打印费用)（净效果与减费一致；与 A Chance
  Encounter 的费用校正思路相同）。
- "控制盟友槽支援时弃置"挂在 CARD_ENTERS_PLAY：任何调查员入场盟友槽
  支援后检查持有者（持续检查的其他入口为引擎缺口，见报告）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import (
    CardType, GameEvent, PlayerClass, SlotType, TimingPriority,
)


class OnYourOwn(CardImplementation):
    card_id = "on_your_own_lv3"

    def _holder(self, game_state):
        for inv in game_state.investigators.values():
            if self.instance_id in inv.play_area:
                return inv
        return None

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.AFTER)
    def discount_survivor_event(self, ctx):
        """你打出求生者事件时：横置孤身一人，返还至多2资源。"""
        card_id = ctx.extra.get("card_id")
        if card_id == self.card_id:
            return
        cd = ctx.game_state.get_card_data(card_id)
        if cd is None or cd.type != CardType.EVENT:
            return
        if cd.card_class != PlayerClass.SURVIVOR:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return
        rebate = min(2, cd.cost or 0)
        if rebate <= 0:
            return  # 0费事件无费可减，不浪费横置
        inst.exhausted = True
        inv.resources += rebate
        ctx.game_state.log_effect(
            f"🧍 孤身一人：横置，事件【{ctx.game_state.card_name(card_id)}】"
            f"费用减免{rebate}资源")

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def discard_if_ally(self, ctx):
        """你控制盟友槽支援时：弃置孤身一人。"""
        holder = self._holder(ctx.game_state)
        if holder is None:
            return
        for iid in holder.play_area:
            if iid == self.instance_id:
                continue
            ci = ctx.game_state.get_card_instance(iid)
            if ci is not None and SlotType.ALLY in (ci.slot_used or []):
                vacate_asset_slots(ctx.game_state, self.instance_id)
                holder.play_area.remove(self.instance_id)
                ctx.game_state.cards_in_play.pop(self.instance_id, None)
                holder.discard.append(self.card_id)
                ctx.game_state.log_effect(
                    "🧍 孤身一人：你控制了盟友，孤身一人被弃置")
                return
