"""Swift Reflexes (Level 0) — Rogue Event. (05156)
快速。在任意调查员的回合中（不含行动中）打出。
立刻进行一个行动，如同在你的回合。这个行动不计入你每回合可进行的行动数。

简化说明：
- "立刻进行一个行动"需要玩家选择任意行动的 UI 流程（会话层缺口），近似为
  打出者 +1 行动点（本回合行动循环中体现；效果等价于"免费多做一个行动"）。
- 打出时机（任意调查员回合、非行动中）校验由会话层负责。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class SwiftReflexes(CardImplementation):
    card_id = "swift_reflexes_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def grant_action(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        inv.actions_remaining += 1
        ctx.extra["swift_reflexes_action"] = True
        ctx.game_state.log_effect("⚡ 迅捷反射：立刻进行一个额外行动（+1行动点）")
