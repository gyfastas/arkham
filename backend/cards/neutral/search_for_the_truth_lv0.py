"""Search for the Truth (Level 0) — Neutral Event.
雷克斯·墨菲牌组专用。抽取X张卡牌，X为雷克斯·墨菲持有的线索数(最多5张)。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class SearchForTheTruth(CardImplementation):
    card_id = "search_for_the_truth_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def draw_cards(self, ctx):
        if ctx.extra.get("card_id") != "search_for_the_truth_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        x = min(getattr(inv, "clues", 0), 5)
        drawn = 0
        for _ in range(x):
            if inv.deck:
                inv.hand.append(inv.deck.pop(0))
                drawn += 1
        ctx.extra["search_for_the_truth_drawn"] = drawn
