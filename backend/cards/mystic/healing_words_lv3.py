"""Healing Words (Level 3) — Mystic Asset, Arcane slot.
使用(4充能)。[action]花费1充能：在你所在地点的调查员之间分配治愈共2点伤害。
"""

from backend.cards.mystic.healing_words_lv0 import HealingWords


class HealingWordsLv3(HealingWords):
    card_id = "healing_words_lv3"
    heal_amount = 2
