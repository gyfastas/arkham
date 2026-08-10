"""David Renfield (Level 0) — Mystic Asset, Ally slot. (03112)
只要大卫·伦费尔德身上有至少1个毁灭标记，你获得+1[willpower]。
[fast] 横置大卫·伦费尔德：你可以在其上放置1个毁灭标记。
其上每有1个毁灭标记，获得1个资源。

简化说明：
- 快速能力的"你可以放置1毁灭"为可选：activate() 默认放置（资源最大化），
  调用方可传 place_doom=False 跳过（规避毁灭推进）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class DavidRenfield(CardImplementation):
    card_id = "david_renfield_lv0"
    activations = [{
        "id": "doom_for_resources",
        "label": "【快速】横置：放置1毁灭，每有1毁灭获得1资源",
        "method": "activate",
    }]

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def willpower_bonus(self, ctx):
        """身上至少1个毁灭标记时：+1意志。"""
        if ctx.skill_type != Skill.WILLPOWER:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is not None and inst.doom >= 1:
            ctx.modify_amount(1, "david_renfield_doom_bonus")

    def activate(self, game_state, investigator_id: str,
                 place_doom: bool = True) -> bool:
        """【快速】横置：（默认）放置1毁灭；其上每有1毁灭获得1资源。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        inst.exhausted = True
        if place_doom:
            inst.doom += 1
        if inst.doom > 0:
            inv.resources += inst.doom
            game_state.log_effect(
                f"💰 大卫·伦费尔德：{inst.doom}个毁灭标记，获得{inst.doom}资源")
        return True
