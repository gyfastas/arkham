"""Take Heart (Level 0) — Survivor Skill. (04201)
每次技能检定最多投入1张。
你可以在任何类型的检定中投入重拾信念。
如果这次检定失败，执行检定的调查员抽取2张卡牌并获得2资源。

简化说明：
- "可投入任何类型检定"为投入窗口规则（本卡无技能图标，官方即如此）；
  效果侧无需区分检定类型。
- "每次检定最多投入1张"由会话层投入窗口约束。
- 抽牌直接取牌堆顶（不经 CARD_DRAWN 钩子，同 perception 从简）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class TakeHeart(CardImplementation):
    card_id = "take_heart_lv0"

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.AFTER)
    def draw_and_gain(self, ctx):
        """检定失败：执行检定的调查员抽2张牌、获得2资源。"""
        if self.card_id not in (ctx.committed_cards or []):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        drawn = 0
        for _ in range(2):
            if inv.deck:
                inv.hand.append(inv.deck.pop(0))
                drawn += 1
        inv.resources += 2
        ctx.extra["take_heart_drawn"] = drawn
        ctx.game_state.log_effect(
            f"💛 重拾信念：检定失败，抽{drawn}张牌并获得2资源")
