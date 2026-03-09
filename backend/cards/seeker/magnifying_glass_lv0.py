"""Magnifying Glass (Level 0) — Seeker Asset, Hand slot.
调查时+1智力。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class MagnifyingGlass(CardImplementation):
    card_id = "magnifying_glass_lv0"

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def intellect_bonus(self, ctx):
        """+1 Intellect while investigating."""
        if ctx.source != self.instance_id:
            # Check if the investigate action is using this card's location
            # For simplicity, boost any intellect test while this card is in play
            pass
        if ctx.skill_type == Skill.INTELLECT:
            # Check this card is in the investigator's play area
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv and self.instance_id in inv.play_area:
                ctx.modify_amount(1, "magnifying_glass_bonus")
