"""Ward of Protection (Level 0) — Mystic Event.
快速。取消一张诡计牌的揭示效果。承受1点恐惧。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class WardOfProtection(CardImplementation):
    card_id = "ward_of_protection_lv0"

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.WHEN,
    )
    def cancel_revelation(self, ctx):
        """Fast. Cancel a treachery's revelation effect. Take 1 horror.

        Skeleton — requires revelation cancel system and horror assignment.
        """
        pass
