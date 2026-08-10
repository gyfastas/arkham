"""Mr. "Rook" (Level 0) — Seeker Asset, Ally slot.
使用(3秘密)。[快速]消耗"老千"先生并花费1秘密：在你牌堆顶部3张、6张或
9张卡牌中查找并抽取任意1张卡牌。如果查找的卡牌中有至少1张弱点，也抽取
其中1张。混洗你的牌堆。

说明：
- 生产环境走会话层两段选择流程（先选深度 3/6/9，再选牌；洗牌已确认）；
  卡文件不提供自动选牌，activate() 必须显式传入 pick（及可选
  weakness_pick），否则返回 False——避免绕开玩家选择。
"""

import random

from backend.cards.base import CardImplementation


class MrRook(CardImplementation):
    card_id = "mr_rook_lv0"

    def activate(self, game_state, investigator_id: str, depth: int = 3,
                 pick: str | None = None,
                 weakness_pick: str | None = None) -> bool:
        """花费1秘密：查找牌堆顶 depth 张，抽取 pick 指定的牌（必选）。

        若查找中有弱点，必须同时抽取其中1张（weakness_pick 指定，
        未指定时取第一张弱点）。其余洗回牌堆。
        """
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted or inst.uses.get("secrets", 0) <= 0:
            return False
        if depth not in (3, 6, 9) or not inv.deck:
            return False

        depth = min(depth, len(inv.deck))
        looked = list(inv.deck[:depth])
        rest = list(inv.deck[depth:])

        if pick is None or pick not in looked:
            return False  # 需要玩家明确选择；UI 走会话层两段流程

        weaknesses = [cid for cid in looked if self._is_weakness(game_state, cid)]
        if pick in weaknesses:
            return False  # 主选必须是非弱点（弱点由强制抽取处理）
        if weaknesses and weakness_pick is None:
            weakness_pick = weaknesses[0]
        if weakness_pick is not None and weakness_pick not in weaknesses:
            return False

        inst.uses["secrets"] -= 1
        inst.exhausted = True

        looked.remove(pick)
        inv.hand.append(pick)
        if weakness_pick is not None:
            looked.remove(weakness_pick)
            inv.hand.append(weakness_pick)

        # 其余洗回牌堆
        inv.deck = rest + looked
        random.shuffle(inv.deck)
        return True

    @staticmethod
    def _is_weakness(game_state, card_id: str) -> bool:
        from backend.models.state import is_weakness_card
        return is_weakness_card(game_state.get_card_data(card_id))
