"""Keen Eye (Level 0) — Guardian Asset. (07152)
[快速]花费2资源：你获得+1[智力]，直到本阶段结束。
[快速]花费2资源：你获得+1[战斗]，直到本阶段结束。

简化说明：
- 两个快速能力实现为公开方法（spend_intellect/spend_combat，会话层调用）；
  可多次支付叠加（官方允许）。
- 加值持续到本阶段结束：在任意阶段结束事件时清除。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class KeenEye(CardImplementation):
    card_id = "keen_eye_lv0"
    activations = [
        {
            "id": "boost_intellect",
            "label": "[快速] 花2资源：本阶段+1智力",
            "method": "spend_intellect",
            "actions": 0,
        },
        {
            "id": "boost_combat",
            "label": "[快速] 花2资源：本阶段+1战斗",
            "method": "spend_combat",
            "actions": 0,
        },
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed: dict[Skill, int] = {}

    def _spend(self, game_state, investigator_id: str, skill: Skill) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None or inv.resources < 2:
            return False
        if self.instance_id not in inv.play_area:
            return False
        inv.resources -= 2
        self._armed[skill] = self._armed.get(skill, 0) + 1
        game_state.log_effect(
            f"👁️ 鹰眼：花2资源，本阶段+1[{skill.value}]"
            f"（累计+{self._armed[skill]}）")
        return True

    def spend_intellect(self, game_state, investigator_id: str) -> bool:
        """[快速] 花2资源：本阶段 +1 智力。"""
        return self._spend(game_state, investigator_id, Skill.INTELLECT)

    def spend_combat(self, game_state, investigator_id: str) -> bool:
        """[快速] 花2资源：本阶段 +1 战斗。"""
        return self._spend(game_state, investigator_id, Skill.COMBAT)

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_boost(self, ctx):
        count = self._armed.get(ctx.skill_type, 0)
        if not count:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ctx.modify_amount(count, "keen_eye_boost")

    @on_event(GameEvent.INVESTIGATION_PHASE_ENDS, priority=TimingPriority.AFTER)
    @on_event(GameEvent.ENEMY_PHASE_ENDS, priority=TimingPriority.AFTER)
    @on_event(GameEvent.MYTHOS_PHASE_ENDS, priority=TimingPriority.AFTER)
    @on_event(GameEvent.UPKEEP_PHASE_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed.clear()
