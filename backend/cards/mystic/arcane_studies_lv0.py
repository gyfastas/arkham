"""Arcane Studies (Level 0) — Mystic Asset.
花费1资源：+1意志力。花费1资源：+1智力。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ArcaneStudies(CardImplementation):
    card_id = "arcane_studies_lv0"

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.WHEN,
    )
    def boost_skill(self, ctx):
        """Spend 1 resource: +1 willpower or +1 intellect.

        Skeleton — requires resource spending UI and skill boost tracking.
        """
        pass
