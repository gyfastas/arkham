"""Grounded (Level 3) — Mystic Asset. (Composure)
快速。场上限制1张[[沉稳]]。
你在[[法术]]卡上的技能检定中+1技能值。
非直接伤害/恐惧必须先分配给脚踏实地，然后才能分配给你的调查员卡。
[fast] 进行[[法术]]卡上的技能检定时，花费1资源：本次检定你+1技能值。

简化说明：
- 继承 lv1（grounded_lv1.Grounded）的恐惧吸收、法术泵与沉稳限制；
  lv3 追加：法术卡检定恒定+1技能值（同泵的 spell 来源判定），以及
  非直接伤害吸收（DAMAGE_ASSIGNED，与恐惧同通道）。
- 已知缺口同 lv1：无来源的法术事件检定识别不到（检定上下文缺发起卡 id）。
"""

from backend.cards.base import on_event
from backend.cards.mystic.grounded_lv1 import Grounded
from backend.models.enums import GameEvent, TimingPriority


class GroundedLv3(Grounded):
    card_id = "grounded_lv3"

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def passive_spell_boost(self, ctx):
        """法术卡上的技能检定恒定+1技能值。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if not self._is_spell_test(ctx):
            return
        ctx.modify_amount(1, "grounded_lv3_passive")

    @on_event(GameEvent.DAMAGE_ASSIGNED, priority=TimingPriority.WHEN)
    def soak_damage(self, ctx):
        """非直接伤害必须先分配给本卡（至多其剩余体力）。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or ctx.amount <= 0:
            return
        cd = ctx.game_state.get_card_data(inst.card_id)
        health = (cd.health if cd else None) or 2  # 数据未填时按印刷值2
        remaining = max(0, health - inst.damage)
        soak = min(remaining, ctx.amount)
        if soak <= 0:
            return
        inst.damage += soak
        ctx.modify_amount(-soak, "grounded_lv3_soak_damage")
        ctx.extra["grounded_lv3_soaked_damage"] = soak
        if inst.damage >= health:
            self._defeat_self(ctx.game_state, inv)
