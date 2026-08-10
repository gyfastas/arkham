"""Savant (Level 1) — Rogue Skill. (08052)
行业专家获得等于（除正在检定的技能外）你最低技能值的[wild]图标。

简化说明：
- 投入时在 SKILL_TEST_COMMIT 追加等量万能图标（印刷的1个[wild]已由
  引擎按 skill_icons 正常计入）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

_ALL_SKILLS = (Skill.WILLPOWER, Skill.INTELLECT, Skill.COMBAT, Skill.AGILITY)


class Savant(CardImplementation):
    card_id = "savant_lv1"

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def add_lowest_skill_icons(self, ctx):
        if self.card_id not in ctx.committed_cards:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        others = [s for s in _ALL_SKILLS if s != ctx.skill_type]
        lowest = min(inv.get_skill(s) for s in others)
        if lowest <= 0:
            return
        ctx.modify_amount(lowest, "savant_icons")
        ctx.extra["savant_icons"] = lowest
        ctx.game_state.log_effect(f"🎓 行业专家：额外+{lowest}万能图标")
