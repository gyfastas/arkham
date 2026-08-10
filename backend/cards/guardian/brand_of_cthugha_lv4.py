"""Brand of Cthugha (Level 4) — Guardian Asset, Arcane slot. (08092)
使用(9充能)。[行动]：攻击。本次攻击你可以使用意志代替战斗，且获得+2技能值。
如果成功，花费1、2或3充能。本次攻击不造成标准伤害，改为每花费1充能造成1点伤害。
如果你成功超出0点，失去2个行动。

简化说明：同 lv1（自动意志替换、自动花费3充能）。
"""

from backend.cards.guardian.brand_of_cthugha_lv1 import BrandOfCthughaLv1


class BrandOfCthughaLv4(BrandOfCthughaLv1):
    card_id = "brand_of_cthugha_lv4"
    skill_bonus = 2
    max_charges_spent = 3
    actions_lost_on_exact = 2
    activations = [{
        "id": "fight",
        "label": "攻击：可用意志代替战斗，+2技能值",
        "method": "activate",
        "actions": 1,
    }]
