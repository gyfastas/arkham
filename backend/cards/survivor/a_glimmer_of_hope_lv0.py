"""A Glimmer of Hope (Level 0) — Survivor Event. Myriad.
希望微光只能从你的弃牌堆打出。
将你弃牌堆中所有希望微光加入你的手牌（包括本卡牌）。

简化说明：
- 引擎的 PLAY 流程只允许从手牌打出（ActionResolver._play 要求 card in hand），
  本卡经公开方法 play_from_discard() 由会话层调用（activations 已声明）：
  支付1资源，将弃牌堆中所有希望微光（含本卡）移回手牌。
- 多重（Myriad，构筑时至多3张）为牌组构筑规则，无运行时效果。
"""

from backend.cards.base import CardImplementation


class AGlimmerOfHope(CardImplementation):
    card_id = "a_glimmer_of_hope_lv0"
    activations = [{
        "id": "play_from_discard",
        "label": "从弃牌堆打出：回收所有希望微光",
        "method": "play_from_discard",
    }]

    def play_from_discard(self, game_state, investigator_id: str) -> bool:
        """从弃牌堆打出：弃牌堆中所有希望微光返回手牌（含本卡）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        copies = [cid for cid in inv.discard if cid == self.card_id]
        if not copies:
            return False
        cd = game_state.get_card_data(self.card_id)
        cost = (getattr(cd, "cost", 1) or 1) if cd else 1
        if inv.resources < cost:
            return False
        inv.resources -= cost
        for _ in copies:
            inv.discard.remove(self.card_id)
            inv.hand.append(self.card_id)
        game_state.log_effect(
            f"🕯️ 希望微光：从弃牌堆打出，{len(copies)}张希望微光返回手牌")
        return True
