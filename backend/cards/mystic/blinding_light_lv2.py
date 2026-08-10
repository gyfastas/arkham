"""Blinding Light (Level 2) — Mystic Event. (01069)
<b>躲避</b>。本次躲避尝试使用[willpower]代替[agility]。如果成功，对刚被躲避的敌人
造成2点伤害。如果本次躲避尝试中揭示了[skull]、[cultist]、[tablet]、[elder_thing]
或[auto_fail]标记，本回合失去1个行动并受到1点恐惧。
"""

from backend.cards.mystic.blinding_light_lv0 import BlindingLight


class BlindingLightLv2(BlindingLight):
    card_id = "blinding_light_lv2"
    damage = 2
    horror_on_bad_token = 1
