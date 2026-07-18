"""Mr. "Rook" (Level 0) — Seeker Asset, Ally slot.
使用(3秘密)。[free]消耗"老千"先生并花费1秘密：在你牌堆顶部3张、6张、或9张卡牌中
查找并抽取任意一张卡牌。如果查找的卡牌中有至少1张弱点，也抽取其中1张。混洗你的牌堆。

简化说明：
- activate(depth) 默认查找顶3张：抽第一张非弱点卡；若其中有弱点也抽第一张弱点；
  其余洗回牌堆。
"""

import random

from backend.cards.base import CardImplementation


class MrRook(CardImplementation):
    card_id = "mr_rook_lv0"

    def activate(self, game_state, investigator_id: str, depth: int = 3) -> bool:
        """花费1秘密：查找牌堆顶 depth 张并抽取。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted or inst.uses.get("secret", 0) <= 0:
            return False
        if depth not in (3, 6, 9) or not inv.deck:
            return False

        inst.uses["secret"] -= 1
        inst.exhausted = True

        depth = min(depth, len(inv.deck))
        looked = inv.deck[:depth]
        rest = inv.deck[depth:]

        # 是否有弱点
        weakness = None
        normal = None
        for cid in looked:
            cd = game_state.get_card_data(cid)
            is_weak = bool(cd and (getattr(cd, "subtype", "") == "weakness"
                                   or "weakness" in (cd.traits or [])))
            if is_weak and weakness is None:
                weakness = cid
            elif not is_weak and normal is None:
                normal = cid

        if normal is not None:
            looked.remove(normal)
            inv.hand.append(normal)
        if weakness is not None:
            looked.remove(weakness)
            inv.hand.append(weakness)

        # 其余洗回牌堆
        inv.deck = rest + looked
        random.shuffle(inv.deck)
        return normal is not None or weakness is not None
