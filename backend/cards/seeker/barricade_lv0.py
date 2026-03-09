"""Barricade (Level 0) — Seeker Event.
附着于你所在地点。非精英敌人无法移动到该地点。
"""

from backend.cards.base import CardImplementation
from backend.models.enums import GameEvent, TimingPriority


class Barricade(CardImplementation):
    card_id = "barricade_lv0"

    # Barricade attaches to a location and prevents non-Elite enemies
    # from moving to that location. This requires:
    # 1. Attachment system (card attaching to location)
    # 2. Enemy movement restriction checks
    # 3. "If any investigator leaves, discard Barricade" rule
    #
    # Skeleton — complex attachment/restriction logic not yet implemented.
    # Would need MOVE_ACTION_INITIATED handler to block enemy movement
    # and CARD_LEAVES_PLAY / investigator move tracking for auto-discard.
    pass
