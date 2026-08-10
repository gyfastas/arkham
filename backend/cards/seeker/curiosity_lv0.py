"""Curiosity (Level 0) — Seeker Skill. (05026)
当你的手牌不少于4张时，好奇心获得[意志][智力]图标（当你的手牌不少于7张时，
改为获得[意志][意志][智力][智力]图标）。

简化说明：
- 动态图标在 SKILL_TEST_COMMIT 结算：仅当检定技能为意志或智力时追加图标
  （另一项图标在任何检定中都不计入，与官方图标规则一致）；
- 手牌数含本次投入的技能牌本身（官方：投入的牌在检定结束前仍在手牌中）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Curiosity(CardImplementation):
    card_id = "curiosity_lv0"

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def bonus_icons(self, ctx):
        """4+手牌+1图标，7+手牌+2图标（意志/智力检定）。"""
        if self.card_id not in (ctx.committed_cards or []):
            return
        if ctx.skill_type not in (Skill.WILLPOWER, Skill.INTELLECT):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        hand = len(inv.hand)
        bonus = 2 if hand >= 7 else (1 if hand >= 4 else 0)
        if bonus:
            ctx.modify_amount(bonus, "curiosity_icons")
            ctx.extra["curiosity_bonus"] = bonus
