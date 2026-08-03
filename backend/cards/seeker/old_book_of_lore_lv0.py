"""Old Book of Lore (Level 0) — Seeker Asset, Hand slot.

官方（Lv0）：行动：选择你所在地点的一名调查员，该调查员抽1张牌（不消耗）。
单人模式即自己。Lv3 的"查看顶3选1"是另一张卡（old_book_of_lore_lv3）。
"""

from backend.cards.base import CardImplementation


class OldBookOfLore(CardImplementation):
    card_id = "old_book_of_lore_lv0"

    activations = [
        {"id": "draw", "label": "行动：抽1张牌", "method": "activate", "actions": 1},
    ]

    def activate(self, game_state, investigator_id: str) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None or not inv.deck:
            return False
        inv.hand.append(inv.deck.pop(0))
        return True
