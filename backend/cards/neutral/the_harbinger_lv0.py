"""The Harbinger (Level 0) — Neutral Treachery, Weakness. (08006)
显现 - 将本卡放置在你的牌堆顶。
先兆被揭示且在你的牌堆顶时，你牌组中的卡牌不能以任何方式被检索、抽取或
操纵，以下能力除外。
[action][action]：丢弃先兆。本能力可以在先兆位于你的牌堆顶时发动，视同
它在你的威胁区域中。

简化说明：
- 牌组锁定由 can_draw_or_search_deck() 供会话层查询（引擎 _draw 与各检索
  卡牌无前置封锁钩子）。
- 显现后直接置于牌堆顶（不经过手牌）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class TheHarbinger(CardImplementation):
    card_id = "the_harbinger_lv0"
    activations = [{"id": "discard", "label": "[行动×2] 丢弃先兆", "method": "activate_discard", "actions": 2}]

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "the_harbinger_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "the_harbinger_lv0" in inv.hand:
            inv.hand.remove("the_harbinger_lv0")
        # 放置在牌堆顶
        inv.deck.insert(0, "the_harbinger_lv0")
        ctx.extra["the_harbinger_on_deck"] = True

    def can_draw_or_search_deck(self, game_state, investigator_id) -> bool:
        """先兆在牌堆顶时：牌组不能被检索、抽取或操纵。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return True
        return not (inv.deck and inv.deck[0] == "the_harbinger_lv0")

    def activate_discard(self, game_state, investigator_id) -> bool:
        """[action][action]：丢弃先兆（可在牌堆顶发动）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        if inv.deck and inv.deck[0] == "the_harbinger_lv0":
            inv.deck.pop(0)
            inv.discard.append("the_harbinger_lv0")
            return True
        # 兜底：在威胁区域时也可丢弃
        for inst_id in list(inv.threat_area):
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "the_harbinger_lv0":
                inv.threat_area.remove(inst_id)
                game_state.cards_in_play.pop(inst_id, None)
                inv.discard.append("the_harbinger_lv0")
                return True
        return False
