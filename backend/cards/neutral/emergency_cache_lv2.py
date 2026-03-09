"""Emergency Cache (Level 2) — Neutral Event.
应急物品（升级版）。获得3资源并抽1张牌。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class EmergencyCacheLv2(CardImplementation):
    card_id = "emergency_cache_lv2"

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.WHEN,
    )
    def gain_resources_and_draw(self, ctx):
        """Gain 3 resources and draw 1 card when played."""
        if ctx.extra.get("card_id") != "emergency_cache_lv2":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv:
            inv.resources += 3
            if inv.deck:
                inv.hand.append(inv.deck.pop(0))
