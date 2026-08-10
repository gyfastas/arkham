"""Scrying (Level 3) — Mystic Asset, Arcane slot. (03236)
使用(3充能)。
[fast] 横置探知术并花费1充能：查看任意一名调查员的牌库或遭遇牌堆顶的3张牌。
将它们以任意顺序放回该牌堆顶。如果查看的牌中有[[Terror]]或[[Omen]]卡，受到1点恐惧。
"""

from backend.cards.mystic.scrying_lv0 import Scrying


class ScryingLv3(Scrying):
    card_id = "scrying_lv3"
    horror_on_terror_or_omen = True
    # 快速能力：不花费行动
    activations = [{
        "id": "scry",
        "label": "【快速】横置+1充能：查看任一牌库或遭遇牌堆顶3张",
        "method": "activate",
    }]
