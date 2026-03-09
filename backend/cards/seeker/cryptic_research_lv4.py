"""Cryptic Research (Level 4) — Seeker Event, Fast.
快速事件：目标调查员抽3张牌。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class CrypticResearch(CardImplementation):
    card_id = "cryptic_research_lv4"

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.WHEN,
    )
    def draw_three(self, ctx):
        """When played, target investigator draws 3 cards."""
        if ctx.extra.get("card_id") != "cryptic_research_lv4":
            return
        target_id = ctx.extra.get("target_id", ctx.investigator_id)
        inv = ctx.game_state.get_investigator(target_id)
        if inv is None:
            return
        cards_to_draw = min(3, len(inv.deck))
        drawn = inv.deck[:cards_to_draw]
        inv.hand.extend(drawn)
        del inv.deck[:cards_to_draw]
