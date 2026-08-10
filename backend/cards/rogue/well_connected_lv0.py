"""Well Connected (Level 0) — Rogue Asset. (05028)
每位调查员限制1张。
[fast] 消耗良好人脉：你每有5资源，这次技能检定你的技能值+1。

简化说明：
- 启动能力经 activations 公开方法实现（会话层 ACTIVATE_CARD 路由）；
  消耗后武装，持有者的下一次技能检定（任意技能）+资源//5，
  SKILL_TEST_ENDS 清除。
- "每位调查员限制1张"为入场规则，引擎无校验通道（引擎缺口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class WellConnected(CardImplementation):
    card_id = "well_connected_lv0"
    activations = [{
        "id": "exhaust_boost",
        "label": "消耗：本次检定每5资源+1技能值",
        "method": "activate",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False

    def activate(self, game_state, investigator_id: str) -> bool:
        """[fast] 消耗：本次技能检定每5资源+1技能值。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or inst.exhausted:
            return False
        if self.instance_id not in inv.play_area:
            return False
        inst.exhausted = True
        self._armed = True
        game_state.log_effect("🎩 良好人脉：消耗，本次检定每5资源+1")
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_boost(self, ctx):
        if not self._armed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        bonus = inv.resources // 5
        if bonus:
            ctx.modify_amount(bonus, "well_connected_boost")
            ctx.extra["well_connected_bonus"] = bonus

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
