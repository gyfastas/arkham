"""Enchanted Blade (Level 3) — Mystic Asset, Hand+Arcane slots. (05193)
使用(4充能)。[action]：攻击。本次攻击+2[combat]。作为使用这个能力的额外费用，
你可以花费最多2充能来为剑附魔（每以此方式花费1充能，本次攻击再+1[combat]
并造成+1伤害）。

简化说明：同 enchanted_blade_lv0。
"""

from backend.cards.mystic.enchanted_blade_lv0 import EnchantedBlade


class EnchantedBladeLv3(EnchantedBlade):
    card_id = "enchanted_blade_lv3"
    base_combat_bonus = 2
    max_empower_charges = 2
