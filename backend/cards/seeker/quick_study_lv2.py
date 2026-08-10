"""Quick Study (Level 2) — Seeker Asset. (04154)
[快速]将你的1个线索放在所在地点上，并消耗一目十行：这次技能检定你的
技能值+3。

简化说明：
- 费用支付为公开方法 spend()（与 ResourceSkillBoost 同模式，由会话层在
  快速窗口调用）：线索放回所在地点并横置本卡，武装下一次检定+3；
- +3 在下一次 SKILL_VALUE_DETERMINED 生效一次，检定结束清除（费用已付
  不退还）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class QuickStudy(CardImplementation):
    card_id = "quick_study_lv2"
    activations = [{
        "id": "spend_clue",
        "label": "[快速]放回1线索并消耗：本次检定+3",
        "method": "spend",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False

    def spend(self, game_state, investigator_id: str) -> bool:
        """[快速]将你的1个线索放在所在地点并消耗本卡：本次检定+3。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted or inv.clues < 1:
            return False
        location = game_state.get_location(inv.location_id)
        if location is None:
            return False
        inv.clues -= 1
        location.clues += 1
        inst.exhausted = True
        self._armed = True
        game_state.log_effect("📚 一目十行：放回1个线索，本次检定+3")
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_boost(self, ctx):
        if not self._armed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ctx.modify_amount(3, "quick_study_boost")
        self._armed = False

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
