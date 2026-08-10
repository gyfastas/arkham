"""Fieldwork (Level 0) — Seeker Asset.
[反应]在你移动到1个地点后，如果该地点有至少1条线索，横置实地考察：
本阶段你执行的下一次技能检定+2技能值。

简化说明：
- MOVE_ACTION_INITIATED 在移动生效前发出（ctx.location_id 为目的地）；
  目的地线索数在移动过程中不变，故直接检查目的地地点；
- 反应自动触发（官方为玩家选择是否横置；横置无其他代价，取最有利分支）；
- +2 在下一次检定的 SKILL_VALUE_DETERMINED 生效一次，阶段结束过期。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Fieldwork(CardImplementation):
    card_id = "fieldwork_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False

    @on_event(GameEvent.MOVE_ACTION_INITIATED, priority=TimingPriority.AFTER)
    def arm_on_move(self, ctx):
        """移动到有线索的地点后：横置，武装下一次检定+2。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return
        dest = ctx.game_state.get_location(ctx.location_id)
        if dest is None or dest.clues < 1:
            return
        inst.exhausted = True
        self._armed = True
        ctx.extra["fieldwork_armed"] = True
        ctx.game_state.log_effect("🧭 实地考察：本阶段下一次技能检定+2")

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def boost_next_test(self, ctx):
        """本阶段下一次技能检定+2（一次性）。"""
        if not self._armed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ctx.modify_amount(2, "fieldwork_boost")
        self._armed = False

    @on_event(GameEvent.INVESTIGATION_PHASE_ENDS, priority=TimingPriority.AFTER)
    def expire(self, ctx):
        """"本阶段"结束：未用的+2过期。"""
        self._armed = False
