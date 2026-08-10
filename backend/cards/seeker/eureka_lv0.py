"""Eureka! (Level 0) — Seeker Skill.
如果本次技能检定成功，执行检定的调查员检索其牌库顶3张牌中的1张，
抽取之，并洗混其牌库。

简化说明：
- 检索选择简化为自动抽取顶3张中的第1张（官方为玩家挑选；
  玩家选择 UI 需会话层接线）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Eureka(CardImplementation):
    card_id = "eureka_lv0"

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def search_top_three(self, ctx):
        """检定成功：检索牌库顶3张，抽1张（自动第1张），洗混牌库。"""
        if self.card_id not in ctx.committed_cards:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or not inv.deck:
            return

        looked = list(inv.deck[:3])
        rest = list(inv.deck[3:])
        pick = looked[0]
        inv.hand.append(pick)
        inv.deck = rest + looked[1:]
        random.shuffle(inv.deck)
        ctx.extra["eureka_drawn"] = pick
        ctx.game_state.log_effect(
            f"💡 发现了！：检定成功，从牌库顶3张中抽到"
            f"【{ctx.game_state.card_name(pick)}】，牌库洗混"
        )
