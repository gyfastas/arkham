"""Armageddon (Level 4) — Mystic Asset, Arcane slot. (07226)
使用(3充能)。[action]花费1充能：攻击。本次攻击使用[willpower]代替[combat]。
本次攻击你+2[willpower]并造成+1伤害。本次攻击中每揭示一个[curse]标记，
你可以对你所在地点的一名敌人造成1点伤害，或在哈米吉多顿上放置1充能。

简化说明：同 armageddon_lv0（curse 奖励自动优先伤害攻击目标，否则放充能）。
"""

from backend.cards.mystic.armageddon_lv0 import Armageddon


class ArmageddonLv4(Armageddon):
    card_id = "armageddon_lv4"
    bonus_willpower = 2
    activations = [{
        "id": "fight",
        "label": "花1充能：用意志攻击，+2意志+1伤害",
        "method": "activate",
        "actions": 1,
    }]
