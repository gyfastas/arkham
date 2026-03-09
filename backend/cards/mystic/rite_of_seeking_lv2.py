"""Rite of Seeking (Level 2) — Mystic Asset, Arcane slot.
使用（3充能）。用意志力+2进行调查。额外发现1条线索。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class RiteOfSeeking(CardImplementation):
    card_id = "rite_of_seeking_lv2"

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.WHEN,
    )
    def investigate_with_willpower(self, ctx):
        """Investigate using willpower +2. Discover 1 additional clue.

        Skeleton — requires investigate override, charge tracking,
        and additional clue discovery.
        """
        pass
