"""Drawn to the Flame (Level 0) — Mystic Event.
抽取遭遇牌组顶牌。在你所在地点发现2条线索。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class DrawnToTheFlame(CardImplementation):
    card_id = "drawn_to_the_flame_lv0"

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.WHEN,
    )
    def discover_clues(self, ctx):
        """Draw top encounter card. Discover 2 clues at your location."""
        if ctx.extra.get("card_id") != "drawn_to_the_flame_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        location = ctx.game_state.get_location(inv.location_id)
        if location:
            clues = min(2, location.clues)
            location.clues -= clues
            inv.clues += clues
