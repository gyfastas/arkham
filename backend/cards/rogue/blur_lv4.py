"""Blur (Level 4) — Rogue Asset, Arcane slot. (08111)
使用(4充能)。
[行动]如果身形虚化还有剩余充能：躲避。这次躲避尝试你可以不使用敏捷，
改为使用意志，并且你+2技能值。如果你成功，花费1或2充能并且这回合你可以
进行等量次数的额外行动。如果你成功且等于难度，受到2点伤害。

简化说明（除数值外同 blur_lv1）：
- "花费1或2充能"简化为自动花费最多2个（有利分支；不足则有多少花多少）。
- 数据笔误兼容：JSON 的 uses 键为 "chargess"，首次访问时规整为 "charges"。
"""

from backend.cards.rogue.blur_lv1 import BlurLv1


class BlurLv4(BlurLv1):
    card_id = "blur_lv4"
    skill_bonus = 2
    max_extra_actions = 2
    zero_margin_damage = 2
