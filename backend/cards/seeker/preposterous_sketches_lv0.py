"""Preposterous Sketches (Level 0) — Seeker Event.
抓3张牌。（打出条件：你所在地点有线索——在打出前检查。）
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class PreposterousSketches(CardImplementation):
    card_id = "preposterous_sketches_lv0"

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.WHEN,
    )
    def draw_three_cards(self, ctx):
        """Draw 3 cards when played.

        Play condition (clue at location) should be validated
        before this card is allowed to be played.
        """
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if ctx.extra.get("card_id") != "preposterous_sketches_lv0":
            return
        for _ in range(3):
            if inv.deck:
                inv.hand.append(inv.deck.pop(0))
