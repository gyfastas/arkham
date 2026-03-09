"""Relic Hunter (Level 3) — Neutral Asset, Permanent.
宝物猎人。永久卡。+1配件栏位。
"""

from backend.cards.base import CardImplementation


class RelicHunter(CardImplementation):
    card_id = "relic_hunter_lv3"
    # Permanent — provides +1 accessory slot.
    # TODO: Implement slot modification in deck-building / setup phase
