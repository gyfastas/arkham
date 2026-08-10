"""Arcane Research (Level 0) — Mystic Asset, Permanent. (04109)
永久。
在你购买奥术研究时，受到1点精神创伤。
在一个剧本的每场冒险结束后，在下一场冒险之前，你升级的第一张[[法术]]
卡牌经验值费用减少1点。

简化说明：
- 永久卡：不涉及对局内结算，无事件处理。战役层接口：
  apply_scenario_start_trauma() 在每场冒险开始时施加精神创伤（1点恐惧）；
  upgrade_discount() 返回下一张法术升级的折扣（每场冒险仅限第一张法术卡，
  用 upgrade_discount_used 标记消费）。
"""

from backend.cards.base import CardImplementation


class ArcaneResearch(CardImplementation):
    card_id = "arcane_research_lv0"
    mental_trauma_on_purchase = 1
    spell_upgrade_discount = 1

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._discount_used = False

    def apply_scenario_start_trauma(self, game_state, investigator_id: str) -> bool:
        """精神创伤：每场冒险开始时受到1点恐惧（战役层调用）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inv.horror += self.mental_trauma_on_purchase
        return True

    def upgrade_discount(self, card_data) -> int:
        """每场冒险第一张[[法术]]升级的经验折扣（消费型）。"""
        if self._discount_used or card_data is None:
            return 0
        traits = [t.lower() for t in (getattr(card_data, "traits", None) or [])]
        if "spell" not in traits:
            return 0
        self._discount_used = True
        return self.spell_upgrade_discount

    def reset_scenario(self) -> None:
        """新一场冒险：重置升级折扣。"""
        self._discount_used = False
