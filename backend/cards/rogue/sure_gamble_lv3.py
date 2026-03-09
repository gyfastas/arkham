"""Sure Gamble (Level 3) — Rogue Event.
老千手法。快速。将混沌标记的负数修正值变为正数。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class SureGamble(CardImplementation):
    card_id = "sure_gamble_lv3"

    # Skeleton: Fast. Play when a chaos token with negative modifier is revealed.
    # Switch negative modifier to positive counterpart.
    # Requires CHAOS_TOKEN_REVEALED handler with token modification
