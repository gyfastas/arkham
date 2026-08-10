"""Scroll of Prophecies (Level 0) — Mystic Asset, Hand slot (Tome).
使用(4秘密)。[action]花费1秘密：选择你所在地点的一位调查员。该调查员抽3张牌，
然后弃掉手牌中的1张牌。

简化说明：
- 弃牌无选择 UI：默认弃掉刚抽到的最后1张（手牌末尾）；可传
  discard_card_id 指定弃哪张。
- 抽牌不触发 CARD_DRAWN 钩子（卡牌代码拿不到 registry/draw_hooks——引擎缺口，
  同 quantum_flux）。
"""

from backend.cards.base import CardImplementation


class ScrollOfProphecies(CardImplementation):
    card_id = "scroll_of_prophecies_lv0"
    activations = [{
        "id": "draw3_discard1",
        "label": "花1秘密：同地点调查员抽3弃1",
        "method": "activate",
        "actions": 1,
    }]

    def activate(self, game_state, investigator_id: str,
                 target_investigator_id: str | None = None,
                 discard_card_id: str | None = None) -> bool:
        """花费1秘密：目标调查员（默认自己，须同地点）抽3张后弃1张。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("secrets", 0) <= 0:
            return False
        target = game_state.get_investigator(target_investigator_id or investigator_id)
        if target is None or target.location_id != inv.location_id:
            return False

        inst.uses["secrets"] -= 1
        for _ in range(3):
            if not target.deck:
                break
            target.hand.append(target.deck.pop(0))

        if not target.hand:
            return True
        if discard_card_id is not None and discard_card_id in target.hand:
            target.hand.remove(discard_card_id)
            target.discard.append(discard_card_id)
        else:
            # 简化：默认弃掉手牌最后1张（刚抽到的）
            target.discard.append(target.hand.pop())
        return True
