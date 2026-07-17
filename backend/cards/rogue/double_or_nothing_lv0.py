"""Double or Nothing (Level 0) — Rogue Skill.
每次技能检定最多投入1张。将该次检定难度加倍。如果检定成功，结算胜利效果两次。

简化说明：
- 难度加倍：引擎的检定难度在 run_test 调用时确定，卡牌无法事后修改，
  本实现在 SKILL_TEST_COMMIT 时把 ctx.difficulty 加倍（供引擎回读，
  若引擎未回读则仅作标记），并记录到 ctx.extra。
- "胜利效果结算两次"简化为：调查成功时额外发现1个线索（若地点还有线索）；
  其他成功效果的双倍结算由会话层按 ctx.extra["double_or_nothing"] 标记处理。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class DoubleOrNothing(CardImplementation):
    card_id = "double_or_nothing_lv0"

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def double_difficulty(self, ctx):
        """投入时：检定难度加倍。"""
        if "double_or_nothing_lv0" not in ctx.committed_cards:
            return
        if ctx.difficulty is not None:
            doubled = ctx.difficulty * 2
            ctx.extra["double_or_nothing_doubled_difficulty"] = doubled
            ctx.difficulty = doubled

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def double_success_effects(self, ctx):
        """成功时：标记双倍结算；调查成功额外发现1个线索。"""
        if "double_or_nothing_lv0" not in ctx.committed_cards:
            return
        ctx.extra["double_or_nothing"] = True
        if ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        location = ctx.game_state.get_location(inv.location_id)
        if location is not None and location.clues > 0:
            location.clues -= 1
            inv.clues += 1
