"""Deduction (Level 0) — Seeker Skill.
提交到智力检定时提供1个智力图标。如果调查检定成功，额外发现1条线索。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Deduction(CardImplementation):
    card_id = "deduction_lv0"

    @on_event(
        GameEvent.SKILL_TEST_SUCCESSFUL,
        priority=TimingPriority.AFTER,
    )
    def extra_clue_on_success(self, ctx):
        """If investigation test is successful, discover 1 additional clue."""
        if "deduction_lv0" not in ctx.committed_cards:
            return
        if ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        location = ctx.game_state.get_location(inv.location_id)
        if location and location.clues > 0:
            location.clues -= 1
            inv.clues += 1
