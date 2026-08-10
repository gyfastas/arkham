"""Wither (Level 4) — Mystic Asset, Arcane slot. (05321)
[action]：攻击。本次攻击使用[willpower]代替[combat]，本次攻击你+2[willpower]。
如果本次攻击中揭示了[skull]、[cultist]、[tablet]或[elder_thing]符号，被攻击的
敌人在本回合剩余时间内-1战斗、-1生命、-1躲避（最低减至1）。

简化说明：同 lv0（减战斗/躲避以降低检定难度实现；-1生命以降低击败阈值实现，
挂debuff时立即检查、后续每次伤害后复查）。数值差异经类属性覆盖。
"""

from backend.cards.mystic.wither_lv0 import Wither


class WitherLv4(Wither):
    card_id = "wither_lv4"
    willpower_bonus = 2
    health_reduction = 1
    activations = [{
        "id": "fight",
        "label": "用意志攻击（+2意志）",
        "method": "activate",
        "actions": 1,
        "target": "enemy",
    }]
