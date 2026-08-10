"""Madame Labranche (Level 0) — Survivor Asset, Ally slot.
[fast] 如果你手牌中没有卡牌，消耗拉布兰奇夫人：抽取1张卡牌。
[fast] 如果你没有资源，消耗拉布兰奇夫人：获得1资源。

简化说明：
- 两个快速能力均为启动式（activations 声明，0行动）：条件满足且未横置时
  横置并结算。抽牌直接取牌堆顶（不经 draw_hooks 的弱点显现流程，与
  guts/lucky_lv2 等既有抽牌实现一致，从简）。
"""

from backend.cards.base import CardImplementation


class MadameLabranche(CardImplementation):
    card_id = "madame_labranche_lv0"
    activations = [
        {
            "id": "draw",
            "label": "快速：无手牌时横置，抽1张牌",
            "method": "activate_draw",
            "actions": 0,
        },
        {
            "id": "gain_resource",
            "label": "快速：无资源时横置，获得1资源",
            "method": "activate_gain_resource",
            "actions": 0,
        },
    ]

    def _ready_and_in_play(self, game_state, investigator_id: str):
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return None, None
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return None, None
        return inv, inst

    def activate_draw(self, game_state, investigator_id: str) -> bool:
        """[fast] 手牌为空时：横置拉布兰奇夫人，抽1张牌。"""
        inv, inst = self._ready_and_in_play(game_state, investigator_id)
        if inv is None or inv.hand:
            return False
        inst.exhausted = True
        if inv.deck:
            card_id = inv.deck.pop(0)
            inv.hand.append(card_id)
            game_state.log_effect(
                f"👒 拉布兰奇夫人：横置，抽到【{game_state.card_name(card_id)}】")
        return True

    def activate_gain_resource(self, game_state, investigator_id: str) -> bool:
        """[fast] 资源为0时：横置拉布兰奇夫人，获得1资源。"""
        inv, inst = self._ready_and_in_play(game_state, investigator_id)
        if inv is None or inv.resources > 0:
            return False
        inst.exhausted = True
        inv.resources += 1
        game_state.log_effect("👒 拉布兰奇夫人：横置，获得1资源")
        return True
