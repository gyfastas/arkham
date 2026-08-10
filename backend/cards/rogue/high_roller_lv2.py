"""High Roller (Level 2) — Rogue Asset. (04156)
[快速]花费3资源并消耗大赌徒：本次技能检定你+2技能值。若你成功，获得3资源。

简化说明：
- activate() 付费3并消耗本卡、武装加值（UI/会话层在检定前调用）；
  随后任意技能类型的检定获得+2，成功时返还3资源。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_COST = 3
_BONUS = 2


class HighRoller(CardImplementation):
    card_id = "high_roller_lv2"
    activations = [{
        "id": "boost",
        "label": "花3资源并消耗：本次检定+2，成功返还3资源",
        "method": "activate",
        "actions": 0,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False

    def activate(self, game_state, investigator_id: str) -> bool:
        """花费3资源并消耗：本次技能检定+2技能值，成功获得3资源。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        if inv.resources < _COST:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        inv.resources -= _COST
        inst.exhausted = True
        self._armed = True
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def skill_boost(self, ctx):
        if not self._armed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ctx.modify_amount(_BONUS, "high_roller_boost")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def refund_on_success(self, ctx):
        """成功：获得3资源。"""
        if not self._armed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inv.resources += _COST
        ctx.extra["high_roller_refund"] = _COST
        ctx.game_state.log_effect("🎰 大赌徒：检定成功，返还3资源")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
