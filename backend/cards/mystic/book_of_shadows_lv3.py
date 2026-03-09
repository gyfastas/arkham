"""Book of Shadows (Level 3) — Mystic Asset, Hand slot.
+1奥术插槽。消耗：为一张法术牌添加1个充能。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class BookOfShadows(CardImplementation):
    card_id = "book_of_shadows_lv3"

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.WHEN,
    )
    def add_arcane_slot_and_charge(self, ctx):
        """+1 arcane slot. Exhaust: Add 1 charge to a Spell asset.

        Skeleton — requires slot expansion and charge management.
        """
        pass
