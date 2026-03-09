"""Grotesque Statue (Level 4) — Mystic Asset, Hand slot.
使用（4充能）。揭示2个混沌标记，选择其中1个。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class GrotesqueStatue(CardImplementation):
    card_id = "grotesque_statue_lv4"

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.WHEN,
    )
    def reveal_two_tokens(self, ctx):
        """Uses (4 charges). Reveal 2 chaos tokens, choose 1.

        Skeleton — requires chaos token reveal override and charge tracking.
        """
        pass
