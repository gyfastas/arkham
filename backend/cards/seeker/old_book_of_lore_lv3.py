"""Old Book of Lore (Level 3) — Seeker Asset, Hand slot.
消耗智慧古书：查看你牌库顶的3张牌。将其中1张加入手牌，其余以任意顺序置于牌库底。
然后，你可以花费1资源：抽取1张牌。

简化说明：
- activate() 将顶3张中第一张加入手牌、其余置于牌库底（选择简化为第一张）；
- pay_to_draw() 实现"花费1资源抽1张"。
"""

from backend.cards.base import CardImplementation


class OldBookOfLoreLv3(CardImplementation):
    card_id = "old_book_of_lore_lv3"

    def activate(self, game_state, investigator_id: str, pick_index: int = 0) -> bool:
        """消耗：查看顶3张，1张加入手牌，其余置于牌库底。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        if not inv.deck:
            return False

        inst.exhausted = True
        top = inv.deck[:3]
        rest = inv.deck[3:]
        pick_index = max(0, min(pick_index, len(top) - 1))
        picked = top.pop(pick_index)
        inv.hand.append(picked)
        inv.deck = rest + top  # 其余置于牌库底
        return True

    def pay_to_draw(self, game_state, investigator_id: str) -> bool:
        """花费1资源：抽取1张牌。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or inv.resources < 1 or not inv.deck:
            return False
        inv.resources -= 1
        inv.hand.append(inv.deck.pop(0))
        return True
