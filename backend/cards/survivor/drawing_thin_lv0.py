"""Drawing Thin (Level 0) — Survivor Asset.
[反应] 你发动一次技能检定时，消耗险中求胜：本次检定难度+2。
获得2资源或抽1张牌。

简化说明：
- SKILL_TEST_BEGINS 即"发动检定"（引擎在该事件允许修改难度）。
- "获得2资源或抽1张牌"自动选择获得2资源（官方为玩家选择；抽牌分支
  可经会话层扩展）。
- 仅控制者本人发动的检定触发；本卡横置后不触发。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class DrawingThin(CardImplementation):
    card_id = "drawing_thin_lv0"

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.REACTION)
    def raise_difficulty_for_payment(self, ctx):
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or inst.owner_id != ctx.investigator_id:
            return
        if self.instance_id not in inv.play_area:
            return
        inst.exhausted = True
        ctx.difficulty = (ctx.difficulty or 0) + 2
        inv.resources += 2
        ctx.extra["drawing_thin"] = True
        ctx.game_state.log_effect(
            "🎲 险中求胜：本次检定难度+2，获得2资源")
