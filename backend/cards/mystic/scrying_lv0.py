"""Scrying (Level 0) — Mystic Asset, Arcane slot.
使用(3充能)。消耗探知术并花费1充能：查看一名调查员牌库顶的3张牌。
该调查员可以将其中任意张置于其牌库底，其余以任意顺序置于其牌库顶。

简化说明：
- activate(bottom_count) 将顶3张中的前 bottom_count 张置于牌库底，
  其余保持顺序置于牌库顶（选择过程由会话层/UI 决定）。
"""

from backend.cards.base import CardImplementation


class Scrying(CardImplementation):
    card_id = "scrying_lv0"
    look_count = 3
    draw_after = False

    def activate(self, game_state, investigator_id: str,
                 target_investigator_id: str | None = None,
                 bottom_count: int = 0) -> bool:
        """花费1充能：查看牌库顶3张并重新排列。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("charges", 0) <= 0:
            return False

        target = game_state.get_investigator(target_investigator_id or investigator_id)
        if target is None or not target.deck:
            return False

        inst.uses["charges"] -= 1
        inst.exhausted = True

        top = target.deck[: self.look_count]
        rest = target.deck[self.look_count:]
        bottom_count = max(0, min(bottom_count, len(top)))
        # 前 bottom_count 张置于牌库底，其余保持顺序在牌库顶
        target.deck = top[bottom_count:] + rest + top[:bottom_count]

        if self.draw_after and target.deck:
            target.hand.append(target.deck.pop(0))
        return True
