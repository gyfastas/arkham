""""老千"先生 Mr. "Rook" (Level 0) — Seeker Asset, Ally slot.
Uses (3 secrets). Free: Exhaust & spend 1 secret: Search top 3/6/9 of deck,
draw 1 card. If weakness found, also draw 1 weakness. Shuffle deck.
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class MrRook(CardImplementation):
    card_id = "mr_rook_lv0"
    # Activation is handled by game_session._activate_asset
