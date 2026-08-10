"""Double or Nothing (Level 0) — Rogue Skill.
每次技能检定最多投入1张。将该次检定难度加倍。如果检定成功，结算胜利效果两次。

简化说明：
- 难度加倍：在 SKILL_TEST_COMMIT 时改写 ctx.difficulty（引擎会回读）。
- "胜利效果结算两次"：
  * 调查成功：额外发现1个线索（若地点还有线索）；
  * 战斗成功：经 ctx.extra["bonus_damage"] 再结算一次全额攻击伤害
    （基础1点 + 已有 bonus_damage 加成）；
  * 其余成功效果（躲避、资源获取等）的双倍结算未实现，
    由会话层按 ctx.extra["double_or_nothing"] 标记处理。
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
        """成功时：标记双倍结算；调查额外发现1线索；战斗双倍伤害。"""
        if "double_or_nothing_lv0" not in ctx.committed_cards:
            return
        ctx.extra["double_or_nothing"] = True
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if ctx.skill_type == Skill.INTELLECT:
            location = ctx.game_state.get_location(inv.location_id)
            if location is not None and location.clues > 0:
                location.clues -= 1
                inv.clues += 1
        elif ctx.skill_type == Skill.COMBAT:
            # 再结算一次攻击伤害：总伤害 = 2 * (基础1 + 已有加成)
            current = int(ctx.extra.get("bonus_damage", 0) or 0)
            ctx.extra["bonus_damage"] = current + 1 + current
