"""Encyclopedia (Level 2) — Seeker Asset, Hand slot.
[行动]消耗百科全书：选择你所在地点的一名调查员。该调查员你选择的一项
技能+2，直到本阶段结束。

简化说明：
- 目标调查员/技能选择需会话层传参：activate() 支持 target_investigator_id
  与 skill 参数；会话层通用通道调用时默认目标为自己、技能为智力。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Encyclopedia(CardImplementation):
    card_id = "encyclopedia_lv2"

    activations = [
        {"id": "boost", "label": "[行动] 消耗：所选技能+2至阶段结束",
         "method": "activate", "actions": 1},
    ]

    def activate(self, game_state, investigator_id: str,
                 target_investigator_id: str | None = None,
                 skill: Skill | None = None) -> bool:
        """消耗：目标调查员所选技能+2，直到本阶段结束。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        target = game_state.get_investigator(target_investigator_id or investigator_id)
        if target is None or target.location_id != inv.location_id:
            return False
        # 简化：会话层通用通道无法传参时默认智力
        skill = skill or Skill.INTELLECT

        inst.exhausted = True
        if not hasattr(target, "active_effects"):
            target.active_effects = {}
        target.active_effects["encyclopedia"] = {
            "skill": skill,
            "amount": 2,
            "source": self.instance_id,
        }
        game_state.log_effect(f"📖 百科全书：所选技能+2（{skill.value}）至阶段结束")
        return True

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def apply_skill_boost(self, ctx):
        """Apply +2 skill bonus if Encyclopedia buff is active for this skill."""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        buff = getattr(inv, "active_effects", {}).get("encyclopedia")
        if buff is None:
            return
        if buff["source"] != self.instance_id:
            return
        if buff["skill"] == ctx.skill_type:
            ctx.modify_amount(buff["amount"], "encyclopedia_boost")

    @on_event(
        GameEvent.INVESTIGATION_PHASE_ENDS,
        priority=TimingPriority.AFTER,
    )
    def expire_buff(self, ctx):
        """Remove Encyclopedia buff at end of phase."""
        for inv in ctx.game_state.investigators.values():
            buff = getattr(inv, "active_effects", {}).get("encyclopedia")
            if buff and buff["source"] == self.instance_id:
                inv.active_effects.pop("encyclopedia", None)
