""".41 Derringer (Level 2) — Rogue Asset, Hand slot.
使用(3弹药)。攻击。你获得+2战斗。如果这次攻击击败该敌人，发现你所在地点1条线索。
如果你成功且超过难度2点以上，本次攻击造成+1伤害。
"""

from backend.cards.rogue.forty_one_derringer_lv0 import FortyOneDerringer


class FortyOneDerringerLv2(FortyOneDerringer):
    card_id = "forty_one_derringer_lv2"
    extra_damage_on_margin = 2
