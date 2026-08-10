"""No Stone Unturned (Level 0) — Seeker Event.
选择你所在地点的1位调查员。该调查员检索其牌库顶6张牌中的1张，
抽取之，并洗混其牌库。

简化说明：
- 目标默认为打出者自己，可用 ctx.extra["target_investigator"] 指定
  （须与打出者同地点）；
- 检索选择简化为自动抽取第1张，可用 ctx.extra["search_pick"] 指定
  （玩家选择 UI 需会话层接线）；
- 牌库不足6张时检索整个牌库。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class NoStoneUnturned(CardImplementation):
    card_id = "no_stone_unturned_lv0"
    search_depth = 6  # lv5 覆盖为 0（整个牌库）

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def search_deck(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        target_id = ctx.extra.get("target_investigator") or inv.investigator_id
        target = ctx.game_state.get_investigator(target_id)
        if target is None or target.location_id != inv.location_id:
            return
        if not target.deck:
            return

        depth = self.search_depth or len(target.deck)
        depth = min(depth, len(target.deck))
        looked = list(target.deck[:depth])
        rest = list(target.deck[depth:])

        pick = ctx.extra.get("search_pick")
        if pick not in looked:
            pick = looked[0]
        looked.remove(pick)
        target.hand.append(pick)
        target.deck = rest + looked
        random.shuffle(target.deck)

        ctx.extra["no_stone_unturned_drawn"] = pick
        ctx.game_state.log_effect(
            f"🔍 翻箱倒柜：检索牌库顶{depth}张，"
            f"抽到【{ctx.game_state.card_name(pick)}】，牌库洗混"
        )
