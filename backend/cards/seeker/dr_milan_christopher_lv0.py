"""Dr. Milan Christopher (Level 0) — Seeker Asset, Ally slot.
在场时+1智力。调查检定成功后获得1资源。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class DrMilanChristopher(CardImplementation):
    card_id = "dr_milan_christopher_lv0"

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def intellect_bonus(self, ctx):
        """+1 Intellect while Dr. Milan is in play."""
        if ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "dr_milan_intellect_bonus")

    @on_event(
        GameEvent.SKILL_TEST_SUCCESSFUL,
        priority=TimingPriority.REACTION,
    )
    def gain_resource_on_investigate(self, ctx):
        """After a successful intellect test (investigation), gain 1 resource."""
        if ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if self.instance_id not in inv.play_area:
            return
        inv.resources += 1
