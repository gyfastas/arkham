""".41 Derringer (Level 2) — Rogue Asset, Hand slot.
使用(3弹药)。[行动]花费1弹药：攻击。本次攻击你获得+2战斗。
若你成功且超出难度1点以上，本次攻击造成+1伤害。
每回合一次，若你成功且超出难度3点以上，你在本回合可以执行1个额外行动。

简化说明：
- 弹药在命中时扣除（同 lv0）。
- "每回合一次"在任意调查员回合开始时重置（skids_otoole 同模式）。
"""

from backend.cards.base import on_event
from backend.cards.rogue.forty_one_derringer_lv0 import FortyOneDerringer
from backend.models.enums import GameEvent, Skill, TimingPriority


class FortyOneDerringerLv2(FortyOneDerringer):
    card_id = "forty_one_derringer_lv2"
    extra_damage_on_margin = 1

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._action_used_this_turn = False

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.WHEN)
    def reset_per_turn(self, ctx):
        self._action_used_this_turn = False

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def extra_action(self, ctx):
        """每回合一次：成功且超出难度3点以上，本回合+1行动。"""
        if ctx.source != self.instance_id:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        if self._action_used_this_turn:
            return
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        if margin < 3:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        inv.actions_remaining += 1
        self._action_used_this_turn = True
        ctx.extra["forty_one_derringer_lv2_extra_action"] = True
