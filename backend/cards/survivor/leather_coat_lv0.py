"""Leather Coat (Level 0) — Survivor Asset, Body slot.
皮大衣。无特殊能力，提供2点生命值伤害吸收。
"""

from backend.cards.base import CardImplementation


class LeatherCoat(CardImplementation):
    card_id = "leather_coat_lv0"
    # No active abilities — provides 2 health soak via body slot.
