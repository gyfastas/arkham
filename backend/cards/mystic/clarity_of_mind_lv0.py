"""Clarity of Mind (Level 0) — Mystic Asset, Arcane slot.
Uses (3 charges). Action, spend 1 charge: Heal 1 horror from an
investigator at your location.
"""

from backend.cards.base import CardImplementation


class ClarityOfMind(CardImplementation):
    card_id = "clarity_of_mind_lv0"
    # Activation is handled by game_session._activate_asset
