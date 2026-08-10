"""Divination (Level 4) — Seeker Asset, Arcane slot. (08103)
使用(6充能)。
[行动]：调查。本次调查中你可以使用[意志]代替[智力]，并获得+2技能值。
如果你成功，花费1、2或3个充能。改为在你所在地点每花费1个充能发现1条线索，
代替原本的1条。如果你以0点差值成功，选择并丢弃你手牌中的2张牌。

实现：与 divination_lv1 共用同一引擎（数值不同）。
"""

from backend.cards.seeker.divination_lv1 import Divination


class DivinationLv4(Divination):
    card_id = "divination_lv4"
    skill_bonus = 2
    max_spend = 3
    zero_margin_discards = 2
