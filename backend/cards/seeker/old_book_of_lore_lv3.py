"""Old Book of Lore (Level 3) — Seeker Asset, Hand slot.
使用(2秘密)。
[行动]消耗智慧古书：选择你所在地点的一名调查员。该调查员查看其牌库顶
的3张牌，抽取其中1张，并洗混其牌库。然后，你可以花费1秘密：令该调查员
立即打出那张牌，其费用-2。

简化说明：
- 目标调查员简化为发动者自己；"查看顶3选1"简化为默认取第1张
  （pick_index 可指定）；
- 第二段"花费1秘密立即以-2费用打出该牌"需要会话层走完整打出流程
  （费用/槽位/事件结算），卡文件无法绕开注册表完成，未实现——已列入
  审计报告待主代理处理（server 侧接线）。
"""

import random

from backend.cards.base import CardImplementation


class OldBookOfLoreLv3(CardImplementation):
    card_id = "old_book_of_lore_lv3"

    activations = [
        {"id": "search", "label": "[行动] 消耗：查看牌库顶3张，抽1张，洗混牌库",
         "method": "activate", "actions": 1},
    ]

    def activate(self, game_state, investigator_id: str,
                 target_investigator_id: str | None = None,
                 pick_index: int = 0) -> bool:
        """消耗：查看目标牌库顶3张，1张加入手牌，洗混牌库。"""
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
        target.deck = rest + top
        random.shuffle(target.deck)
        game_state.log_effect(f"📚 智慧古书(3)：抽取【{game_state.card_name(picked)}】并洗混牌库")
        return True
