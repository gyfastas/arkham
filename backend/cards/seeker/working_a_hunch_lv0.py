"""Working a Hunch (Level 0) — Seeker Event, Fast.
快速事件：在你所在地点发现1条线索（无需检定）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class WorkingAHunch(CardImplementation):
    card_id = "working_a_hunch_lv0"

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.WHEN,
    )
    def discover_clue(self, ctx):
        """When played, discover 1 clue at your location (no test)."""
        if ctx.extra.get("card_id") != "working_a_hunch_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        location = ctx.game_state.get_location(inv.location_id)
        if location and location.clues > 0:
            location.clues -= 1
            inv.clues += 1
