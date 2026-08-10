"""Patrice's Violin (Level 0) — Neutral Asset. (06016)
仅限帕特里斯·海瑟薇牌组。
[fast]选择并丢弃1张你的手牌并横置帕特里斯的小提琴：选择你所在地点的一名
调查员，其获得1个资源或抽1张牌。

简化说明：
- "仅限帕特里斯牌组"为构筑限制，由卡组校验负责。
- 目标与效果（资源/抽牌）由会话层传入；缺省目标为持有者本人、效果为资源。
"""

from backend.cards.base import CardImplementation


class PatricesViolin(CardImplementation):
    card_id = "patrices_violin_lv0"
    activations = [{
        "id": "serenade",
        "label": "[快速] 丢1张手牌并横置：同地点调查员获1资源或抽1牌",
        "method": "activate",
        # fast：不耗行动
    }]

    def activate(
        self,
        game_state,
        investigator_id: str,
        discard_card_id: str | None = None,
        target_investigator_id: str | None = None,
        effect: str = "resource",
    ) -> bool:
        """[fast] 丢弃1张手牌并横置：同地点调查员获得1资源或抽1张牌。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        if inst.exhausted:
            return False
        if not inv.hand:
            return False
        # 简化：缺省弃第一张手牌（官方为玩家选择）
        if discard_card_id is None:
            discard_card_id = inv.hand[0]
        if discard_card_id not in inv.hand:
            return False

        target = game_state.get_investigator(target_investigator_id or investigator_id)
        if target is None or target.location_id != inv.location_id:
            return False

        inst.exhausted = True
        inv.hand.remove(discard_card_id)
        inv.discard.append(discard_card_id)

        if effect == "draw":
            if target.deck:
                target.hand.append(target.deck.pop(0))
        else:
            target.resources += 1
        return True
