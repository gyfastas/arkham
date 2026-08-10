"""Survey the Area (Level 1) — Seeker Skill. (08037)
只要地区勘测在你手中或被投入到技能检定中，其获得等于你[agility]的
[intellect]图标，以及等于你[intellect]的[agility]图标。

简化说明：
- 图标在投入时按你当前的敏捷/智力值动态结算（SKILL_TEST_COMMIT 补加；
  引擎静态图标表为空，避免重复计数）：智力检定 +你敏捷值，敏捷检定
  +你智力值，其它检定 +0。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class SurveyTheArea(CardImplementation):
    card_id = "survey_the_area_lv1"

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def swapped_icons(self, ctx):
        if self.card_id not in ctx.committed_cards:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if ctx.skill_type == Skill.INTELLECT:
            bonus = inv.get_skill(Skill.AGILITY)
        elif ctx.skill_type == Skill.AGILITY:
            bonus = inv.get_skill(Skill.INTELLECT)
        else:
            bonus = 0
        if bonus > 0:
            ctx.modify_amount(bonus, "survey_the_area_icons")
            ctx.extra["survey_the_area_icons"] = bonus
