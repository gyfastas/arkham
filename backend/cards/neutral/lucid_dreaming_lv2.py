"""Lucid Dreaming (Level 2) — Neutral Event.
选择你战场上的1张牌，或展示你手牌中的1张牌。从你的牌库中搜寻该牌的
另一张复制并抽取之。洗混你的牌组。

简化说明：
- 目标选择需玩家输入：可用 ctx.extra["target_card_id"] 指定；
  默认选择手牌第一张（无手牌则战场第一张）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class LucidDreaming(CardImplementation):
    card_id = "lucid_dreaming_lv2"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def search_copy(self, ctx):
        if ctx.extra.get("card_id") != "lucid_dreaming_lv2":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or not inv.deck:
            return

        target_id = ctx.extra.get("target_card_id")
        if target_id is None:
            if inv.hand:
                target_id = inv.hand[0]
            else:
                for iid in inv.play_area:
                    inst = ctx.game_state.get_card_instance(iid)
                    if inst is not None:
                        target_id = inst.card_id
                        break
        if target_id is None:
            return

        # 搜寻牌库中的另一张复制
        for i, cid in enumerate(inv.deck):
            if cid == target_id:
                inv.deck.pop(i)
                inv.hand.append(cid)
                random.shuffle(inv.deck)
                ctx.game_state.log_effect(
                    f"💭 清醒梦：从牌库搜寻到【{ctx.game_state.card_name(cid)}】"
                    "并抽取，牌库洗混"
                )
                ctx.extra["lucid_dreaming_drawn"] = cid
                return
        ctx.game_state.log_effect("💭 清醒梦：牌库中没有该牌的复制")
