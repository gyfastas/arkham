"""Charisma (Level 3) — Neutral Asset, Permanent.
魅力超凡。永久卡。+1同盟栏位。
"""

from backend.cards.base import CardImplementation


class Charisma(CardImplementation):
    card_id = "charisma_lv3"
    # Permanent — provides +1 ally slot.
    # TODO: Implement slot modification in deck-building / setup phase
