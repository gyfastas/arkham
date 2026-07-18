"""First Aid (Level 3) — Guardian Asset.
消耗急救并花费1资源：治愈你所在地点的一名调查员或盟友3点伤害。
"""

from backend.cards.guardian.first_aid_lv0 import FirstAid


class FirstAidLv3(FirstAid):
    card_id = "first_aid_lv3"
    activations = [{"id": "heal", "label": "消耗+1资源：治愈3伤害", "method": "activate"}]
    heal_amount = 3
