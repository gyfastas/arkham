"""Tennessee Sour Mash (Level 3) — Rogue Asset. (05190)
快速。使用(2补给)。
[fast] 消耗田纳西酸麦芽威士忌并花费1补给：你在诡计卡的一次技能检定中+3意志。
[action] 丢弃田纳西酸麦芽威士忌：攻击。你这次攻击+3战斗并造成+1伤害。

简化说明：
- 继承 rogue lv0 实现，仅加值不同（意志+3、攻击+3战斗/+1伤害）；"快速"
  指打出本卡不花行动，由卡牌数据 fast 标记经引擎自动处理。
- 注意：本卡(05190)与 survivor/tennessee_sour_mash_lv3.json(05191)共用
  card_id "tennessee_sour_mash_lv3"，注册表只能保留其一（数据层冲突，
  见批次报告）；直接 import 本类不受影响。
"""

from backend.cards.rogue.tennessee_sour_mash_lv0 import TennesseeSourMashRogue


class TennesseeSourMashRogueLv3(TennesseeSourMashRogue):
    card_id = "tennessee_sour_mash_lv3"
    willpower_bonus = 3
    combat_bonus = 3
    bonus_damage = 1
    activations = [
        {
            "id": "steady_nerves",
            "label": "消耗+1补给：下次意志检定+3",
            "method": "activate_willpower",
        },
        {
            "id": "brawl",
            "label": "丢弃：攻击+3战斗/+1伤害",
            "method": "activate_fight",
            "actions": 1,
            "target": "enemy",
        },
    ]
