"""Blinding Light (Level 2) — Mystic Event.
法术。躲避。本次躲避使用意志代替敏捷。你获得+4敏捷。
"""

from backend.cards.mystic.blinding_light_lv0 import BlindingLight


class BlindingLightLv2(BlindingLight):
    card_id = "blinding_light_lv2"
    bonus = 4
    return_on_margin = 999  # lv2 无返回效果
