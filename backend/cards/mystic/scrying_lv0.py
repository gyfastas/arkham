"""Scrying (Level 0) — Mystic Asset, Arcane slot.
使用（3充能）。查看任意牌组顶部3张牌，重新排列。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Scrying(CardImplementation):
    card_id = "scrying_lv0"

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.WHEN,
    )
    def scry_top_cards(self, ctx):
        """Look at top 3 cards of any deck, reorder them.

        Skeleton — requires deck peek UI and charge tracking.
        """
        pass
