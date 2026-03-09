"""Scrying (Level 3) — Mystic Asset, Arcane slot.
使用（3充能）。快速。查看任意牌组顶部3张牌。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ScryingLv3(CardImplementation):
    card_id = "scrying_lv3"

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.WHEN,
    )
    def scry_top_cards(self, ctx):
        """Fast. Look at top 3 cards of any deck.

        Skeleton — requires deck peek UI and charge tracking.
        """
        pass
