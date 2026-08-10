"""Bandages (Level 0) — Survivor Asset.
使用(3补给)。如果绷带没有补给，弃置它。
[反应] 你所在地点的一位调查员或一张[[盟友]]支援卡受到至少1点伤害后，
花费1补给：治愈该卡牌1点伤害。

简化说明：
- 调查员承伤经 DAMAGE_ASSIGNED(AFTER) 触发：若目标调查员与绷带控制者
  同地点且实际承伤≥1，自动花费1补给治愈其1点伤害（官方为玩家选择时机；
  一次多点伤害也仅治愈1点，与官方"1 or more damage → heal 1"一致）。
- 盟友支援卡承伤无引擎事件（盟友分摊在 DamageEngine 内部完成，不发事件），
  该分支为引擎缺口（见报告），当前仅覆盖调查员承伤。
- 补给耗尽时弃置绷带。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, TimingPriority


class Bandages(CardImplementation):
    card_id = "bandages_lv0"
    supplies_key = "supplies"

    def _supplies(self, inst) -> int:
        # 数据文件键名为 "suppliess"（数据源笔误），两种键名都兼容
        return inst.uses.get(self.supplies_key, inst.uses.get("suppliess", 0))

    @on_event(GameEvent.DAMAGE_ASSIGNED, priority=TimingPriority.AFTER)
    def heal_damage(self, ctx):
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        owner = ctx.game_state.get_investigator(inst.owner_id)
        target = ctx.game_state.get_investigator(ctx.investigator_id)
        if owner is None or target is None:
            return
        if self.instance_id not in owner.play_area:
            return
        if target.location_id != owner.location_id:
            return
        if (ctx.amount or 0) < 1:
            return
        if self._supplies(inst) <= 0:
            return

        key = self.supplies_key if self.supplies_key in inst.uses else "suppliess"
        inst.uses[key] -= 1
        # 治愈1点伤害：经减少承伤量表达（事件发出时伤害尚未应用到调查员，
        # 引擎按减少量结算调查员承受部分，净效果与"受到后治愈1点"一致）
        ctx.modify_amount(-1, "bandages_heal")
        ctx.game_state.log_effect(
            f"🩹 绷带：花费1补给，治愈{ctx.investigator_id}的1点伤害")
        if self._supplies(inst) <= 0:
            vacate_asset_slots(ctx.game_state, self.instance_id)
            owner.play_area.remove(self.instance_id)
            ctx.game_state.cards_in_play.pop(self.instance_id, None)
            owner.discard.append(self.card_id)
            ctx.game_state.log_effect("🩹 绷带：补给耗尽，弃置绷带")
