"""Emergency Cache (Level 0) — Neutral Event.
获得3资源。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class EmergencyCache(CardImplementation):
    card_id = "emergency_cache_lv0"

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.AFTER,
    )
    def gain_resources(self, ctx):
        """Gain 3 resources when played."""
        if ctx.extra.get("card_id") != "emergency_cache_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv:
            inv.resources += 3
