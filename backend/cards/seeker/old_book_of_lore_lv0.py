"""Old Book of Lore (Level 0) — Seeker Asset, Hand slot.
[行动]消耗智慧古书：选择你所在地点的一名调查员。该调查员查看其牌库顶
的3张牌，抽取其中1张，并将其余的牌洗入其牌库。

简化说明：
- 目标调查员简化为发动者自己（多人局目标选择需会话层传参）；
- "查看顶3选1"简化为默认取第1张（pick_index 可指定）；生产环境由会话层
  两段选择流程呈现，但会话特判目前将未选牌置于牌库底而非洗混
  （server/game_session.py，已列入审计报告待主代理处理）。
"""

import random

from backend.cards.base import CardImplementation


class OldBookOfLore(CardImplementation):
    card_id = "old_book_of_lore_lv0"

    activations = [
        {"id": "search", "label": "[行动] 消耗：查看牌库顶3张，抽1张，其余洗混",
         "method": "activate", "actions": 1},
    ]

    def activate(self, game_state, investigator_id: str,
                 target_investigator_id: str | None = None,
                 pick_index: int = 0) -> bool:
        """消耗：查看目标牌库顶3张，1张加入手牌，其余洗入牌库。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        target = game_state.get_investigator(target_investigator_id or investigator_id)
        if target is None or target.location_id != inv.location_id:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        if not target.deck:
            return False

        inst.exhausted = True
        top = list(target.deck[:3])
        rest = list(target.deck[3:])
        pick_index = max(0, min(pick_index, len(top) - 1))
        picked = top.pop(pick_index)
        target.hand.append(picked)
        # 其余的牌洗入牌库
        target.deck = rest + top
        random.shuffle(target.deck)
        game_state.log_effect(f"📚 智慧古书：抽取【{game_state.card_name(picked)}】，其余洗入牌库")
        return True
