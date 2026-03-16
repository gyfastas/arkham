"""Liquid Courage (Level 0) — Rogue Asset, no slot.
Uses (4 supplies). Action, spend 1 supply: Heal 1 horror from an
investigator at your location. That investigator tests willpower (2).
Success: heal 1 additional horror. Failure: discard 1 random hand card.
"""

from backend.cards.base import CardImplementation


class LiquidCourage(CardImplementation):
    card_id = "liquid_courage_lv0"
    # Activation is handled by game_session._activate_asset
