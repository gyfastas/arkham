"""Bulletproof Vest (Level 3) — Neutral Asset, Body slot.
防弹衣。无特殊能力，提供4点生命值伤害吸收。
"""

from backend.cards.base import CardImplementation


class BulletproofVest(CardImplementation):
    card_id = "bulletproof_vest_lv3"
    # No active abilities — provides 4 health soak via body slot.
