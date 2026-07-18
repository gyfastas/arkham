"""Scrying (Level 3) — Mystic Asset, Arcane slot.
使用(3充能)。同探知术(0级)，然后该调查员抽取1张牌。
"""

from backend.cards.mystic.scrying_lv0 import Scrying


class ScryingLv3(Scrying):
    card_id = "scrying_lv3"
    draw_after = True
