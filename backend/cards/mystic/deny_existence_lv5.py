"""Deny Existence (Level 5) — Mystic Event. (05280)
快速。在一张遭遇卡或一次敌人攻击将会导致你执行以下一项（选择一项）时打出：
丢弃手牌、失去资源、失去行动、受到伤害或受到恐惧。你忽略该效果的那个方面。
然后，对应地执行与之相反的效果（抽取卡牌、获得资源、获得额外行动、
治愈伤害或治愈恐惧）。

简化说明：同 deny_existence_lv0；lv5 在忽略后治愈等量伤害/恐惧。
（抽牌/得资源/加行动方面无引擎事件通道——引擎缺口。）
"""

from backend.cards.mystic.deny_existence_lv0 import DenyExistence


class DenyExistenceLv5(DenyExistence):
    card_id = "deny_existence_lv5"
    reverse_effect = True
