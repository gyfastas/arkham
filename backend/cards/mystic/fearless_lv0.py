"""Fearless (Level 0) — Mystic Skill.
成功时治愈1点恐惧。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Fearless(CardImplementation):
    card_id = "fearless_lv0"

    @on_event(
        GameEvent.SKILL_TEST_SUCCESSFUL,
        priority=TimingPriority.AFTER,
    )
    def heal_horror(self, ctx):
        """If successful, heal 1 horror from the investigator."""
        if "fearless_lv0" not in getattr(ctx, 'committed_cards', []):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and inv.horror > 0:
            inv.horror -= 1
