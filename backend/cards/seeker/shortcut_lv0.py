"""Shortcut (Level 0) — Seeker Event, Fast.
快速事件：将你所在地点的一名调查员移动到一个连接地点。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Shortcut(CardImplementation):
    card_id = "shortcut_lv0"

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.WHEN,
    )
    def move_investigator(self, ctx):
        """Move an investigator at your location to a connecting location.

        Skeleton — requires target selection UI for choosing
        the investigator and the destination location.
        """
        pass
