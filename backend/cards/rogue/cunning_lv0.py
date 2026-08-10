"""Cunning (Level 0) — Rogue Skill. (05030)
只要你拥有至少5资源，狡猾获得[智力][敏捷]（只要你拥有至少10资源，改为
狡猾获得[智力][智力][敏捷][敏捷]）。

实现说明：
- 印刷图标为[智力][敏捷]各1；获得的图标同样是智力/敏捷，故仅在智力或
  敏捷检定中提供加值（5+资源 +2，10+资源 +4；其他技能检定无加成）。
- 在 SKILL_TEST_COMMIT 经 ctx.modify_amount 叠加（引擎回读为投入图标）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Cunning(CardImplementation):
    card_id = "cunning_lv0"

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def bonus_icons(self, ctx):
        """按资源数获得额外图标：5+ → +2，10+ → +4（仅智力/敏捷检定）。"""
        if self.card_id not in (ctx.committed_cards or []):
            return
        if ctx.skill_type not in (Skill.INTELLECT, Skill.AGILITY):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if inv.resources >= 10:
            ctx.modify_amount(4, "cunning_10_resources")
        elif inv.resources >= 5:
            ctx.modify_amount(2, "cunning_5_resources")
