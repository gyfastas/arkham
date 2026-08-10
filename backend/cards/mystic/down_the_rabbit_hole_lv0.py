"""Down the Rabbit Hole (Level 0) — Mystic Asset, Permanent. (08059)
永久。每副牌组限制1张。当牌组构建时购买。
在一个剧本的每场冒险结束后，在下一场冒险之前，你升级的前2张卡牌经验值
费用减1。
你购买新卡牌的经验值费用加1。

简化说明：
- 永久卡：不涉及对局内结算，无事件处理。战役层接口：
  upgrade_discount() 返回下一张升级的折扣（每场冒险前2张，消费型计数）；
  new_card_purchase_penalty 为购买新卡的经验惩罚（恒定+1）。
"""

from backend.cards.base import CardImplementation


class DownTheRabbitHole(CardImplementation):
    card_id = "down_the_rabbit_hole_lv0"
    upgrades_discounted_per_scenario = 2
    upgrade_discount_amount = 1
    new_card_purchase_penalty = 1

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._discounts_left = self.upgrades_discounted_per_scenario

    def upgrade_discount(self) -> int:
        """每场冒险前2张升级的经验折扣（消费型）。"""
        if self._discounts_left <= 0:
            return 0
        self._discounts_left -= 1
        return self.upgrade_discount_amount

    def new_card_cost_modifier(self) -> int:
        """购买新卡（非升级）的经验惩罚：+1。"""
        return self.new_card_purchase_penalty

    def reset_scenario(self) -> None:
        """新一场冒险：重置2次升级折扣额度。"""
        self._discounts_left = self.upgrades_discounted_per_scenario
