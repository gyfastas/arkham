"""Shroud of Shadows (Level 4) — Mystic Asset, Arcane slot. (07228)
使用(3充能)。
[action]花费1充能：躲避。本次躲避使用[willpower]代替[agility]，本次检定+2[willpower]。
如果成功且被躲避的敌人非[[精英]]，你可以将该敌人移动到一个连接地点。本次躲避中
每揭示1个[curse]标记，你可以移动到一个连接地点，或在本卡上放置1充能。

简化说明：同 lv0（敌人移动自动选第一个连接地点；curse 奖励自动选放置充能，
按揭示的 curse 数量逐充能放置）。数值差异经类属性覆盖。
"""

from backend.cards.mystic.shroud_of_shadows_lv0 import ShroudOfShadows


class ShroudOfShadowsLv4(ShroudOfShadows):
    card_id = "shroud_of_shadows_lv4"
    willpower_bonus = 2
    charge_per_curse = True
    activations = [{
        "id": "evade",
        "label": "花1充能：用意志躲避（+2意志）",
        "method": "activate",
        "actions": 1,
        "target": "enemy",
    }]
