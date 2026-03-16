"""Peter Sylvestre (Level 0) — Survivor Asset, Ally slot.
Passive: +1 agility.
Reaction: After your turn ends, heal 1 horror from Peter Sylvestre.
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class PeterSylvestre(CardImplementation):
    card_id = "peter_sylvestre_lv0"

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def agility_bonus(self, ctx):
        """+1 Agility while Peter Sylvestre is in play."""
        if ctx.skill_type != Skill.AGILITY:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "peter_sylvestre_agility")
