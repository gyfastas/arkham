"""Arcane Initiate (Level 0) — Mystic Asset, Ally slot.
强制：进场时放置1个毁灭标记。消耗：检索牌组顶部3张中的法术牌，抓取之。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ArcaneInitiate(CardImplementation):
    card_id = "arcane_initiate_lv0"

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.WHEN,
    )
    def enter_play(self, ctx):
        """Forced: Place 1 doom when entering play. Exhaust: Search top 3 for Spell.

        Skeleton — requires doom placement, exhaust tracking, and deck search.
        """
        pass
