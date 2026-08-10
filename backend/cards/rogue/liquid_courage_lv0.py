"""Liquid Courage (Level 0) — Rogue Asset.
使用(4补给)。[action]花费1补给：选择你所在地点的一位调查员，治愈1点恐惧。
然后，该调查员检定[willpower](2)。如果检定成功，该调查员额外治愈1点恐惧。
如果检定失败，该调查员随机丢弃1张手牌。

简化说明：
- activate() 先治愈1点恐惧；resolve_test(success) 由会话层在意志检定后调用。
"""

import random

from backend.cards.base import CardImplementation


class LiquidCourage(CardImplementation):
    card_id = "liquid_courage_lv0"
    activations = [{"id": "heal", "label": "花1补给：治愈1恐惧", "method": "activate"}]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._rng = random.Random()

    def activate(self, game_state, investigator_id: str,
                 target_investigator_id: str | None = None) -> bool:
        """花费1补给：治愈目标1点恐惧。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("supplies", 0) <= 0:
            return False
        target = game_state.get_investigator(target_investigator_id or investigator_id)
        if target is None:
            return False
        if target.location_id != inv.location_id:
            return False
        # 目标满恐惧时仍可发动（治愈无效，仍做意志检定）
        inst.uses["supplies"] -= 1
        if target.horror > 0:
            target.horror -= 1
        return True

    def resolve_test(self, game_state, investigator_id: str, success: bool) -> None:
        """意志(2)检定结算：成功再治愈1点恐惧；失败随机弃1张手牌。"""
        target = game_state.get_investigator(investigator_id)
        if target is None:
            return
        if success:
            if target.horror > 0:
                target.horror -= 1
        else:
            if target.hand:
                idx = self._rng.randrange(len(target.hand))
                card_id = target.hand.pop(idx)
                target.discard.append(card_id)
