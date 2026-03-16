"""Rite of Seeking (Level 0) — Mystic Asset, Arcane slot.
Uses (3 charges). Action, spend 1 charge: Investigate using willpower
instead of intellect. If successful, discover 1 additional clue.
"""

from backend.cards.base import CardImplementation


class RiteOfSeeking(CardImplementation):
    card_id = "rite_of_seeking_lv0"
    # Activation is handled by game_session._activate_asset
