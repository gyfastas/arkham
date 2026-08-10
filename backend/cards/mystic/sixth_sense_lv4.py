"""Sixth Sense (Level 4) — Mystic Asset, Arcane slot. (05322)
[action]：调查。不使用[intellect]，改为使用[willpower]调查，本次调查+2[willpower]。
如果本次检定中揭示了[skull]、[cultist]、[tablet]或[elder_thing]符号，你可以选择
与你所在地点相距至多2条连接的一个已揭示地点；如同你在所在地点调查的同时，也在
所选地点调查（你可以使用两个地点中任意一个的隐藏值）。

简化说明：同 lv0（目标地点自动选隐藏值最低者；低隐藏值以等效技能加值实现）。
lv4 为"同时"调查：本地点线索正常发现，目标地点线索为额外发现（有线索时）。
"""

from backend.cards.mystic.sixth_sense_lv0 import SixthSense


class SixthSenseLv4(SixthSense):
    card_id = "sixth_sense_lv4"
    willpower_bonus = 2
    max_connections = 2
    in_addition = True
    activations = [{
        "id": "investigate",
        "label": "用意志调查（+2意志）",
        "method": "activate",
        "actions": 1,
    }]
