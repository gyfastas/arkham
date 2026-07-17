"""Hired Muscle (Level 1) — Rogue Asset, Ally slot.
你获得+1[combat]。
强制 - 当补给阶段结束时：你必须选择丢弃1资源，或丢弃雇佣打手。

简化说明：
- 补给阶段的"选择"自动结算：有资源则扣1，否则丢弃雇佣打手。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class HiredMuscle(CardImplementation):
    card_id = "hired_muscle_lv1"

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """雇佣打手在场时 +1 战斗。"""
        if ctx.skill_type != Skill.COMBAT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "hired_muscle_combat")

    @on_event(GameEvent.UPKEEP_PHASE_ENDS, priority=TimingPriority.AFTER)
    def upkeep_payment(self, ctx):
        """补给阶段结束：丢弃1资源，否则丢弃雇佣打手。"""
        for inv in ctx.game_state.investigators.values():
            if self.instance_id not in inv.play_area:
                continue
            if inv.resources >= 1:
                inv.resources -= 1
            else:
                inv.play_area.remove(self.instance_id)
                ctx.game_state.cards_in_play.pop(self.instance_id, None)
                inv.discard.append("hired_muscle_lv1")
