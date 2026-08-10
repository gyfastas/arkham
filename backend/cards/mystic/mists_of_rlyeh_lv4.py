"""Mists of R'lyeh (Level 4) — Mystic Asset, Arcane slot.
使用(5充能)。[action]花费1充能：躲避。本次躲避使用[willpower]代替[agility]，
且本次躲避+3[willpower]。如果成功，躲避所选敌人后，你可以移动到1个连接地点。
如果本次躲避中揭示了[skull]、[cultist]、[tablet]、[elder_thing]或[auto_fail]
标记，选择并弃掉你手牌中的1张牌。

简化说明：同 lv0（移动自动选首个连接地点；坏标记自动弃手牌最后1张）。
"""

from backend.cards.mystic.mists_of_rlyeh_lv0 import MistsOfRlyeh


class MistsOfRlyehLv4(MistsOfRlyeh):
    card_id = "mists_of_rlyeh_lv4"
    willpower_bonus = 3
