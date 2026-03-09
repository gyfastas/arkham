"""Elder Sign Amulet (Level 3) — Neutral Asset, Accessory slot.
远古印记护身符。无特殊能力，提供4点理智值恐惧吸收。
"""

from backend.cards.base import CardImplementation


class ElderSignAmulet(CardImplementation):
    card_id = "elder_sign_amulet_lv3"
    # No active abilities — provides 4 sanity soak via accessory slot.
