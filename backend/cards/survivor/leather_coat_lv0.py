"""Leather Coat (Level 0) — Survivor Asset, Body slot.
你获得+2生命值。
"""

from backend.cards.neutral.bulletproof_vest_lv3 import BulletproofVest


class LeatherCoat(BulletproofVest):
    card_id = "leather_coat_lv0"
    health_bonus = 2
