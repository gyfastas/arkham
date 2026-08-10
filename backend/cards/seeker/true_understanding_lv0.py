"""True Understanding (Level 0) — Seeker Skill. (04153)
只能投入冒险卡上打印的能力中的技能检定。
如果本次技能检定成功，发现你所在地点的1个线索。

简化说明：
- "只能投入冒险卡能力检定"为投入限制：引擎/会话层的检定上下文目前没有
  "检定来自冒险卡"的标记（引擎缺口，见报告）；本实现只在成功时结算
  发现线索效果，投入合法性由会话层校验。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class TrueUnderstanding(CardImplementation):
    card_id = "true_understanding_lv0"

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def discover_clue(self, ctx):
        """检定成功：发现你所在地点的1个线索。"""
        if self.card_id not in ctx.committed_cards:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        location = ctx.game_state.get_location(inv.location_id)
        if location is not None and location.clues > 0:
            location.clues -= 1
            inv.clues += 1
            ctx.extra["true_understanding_clue"] = True
            ctx.game_state.log_effect("📖 参透真谛：检定成功，发现1条线索")
