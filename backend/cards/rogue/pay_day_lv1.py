"""Pay Day (Level 1) — Rogue Event. (04233)
你获得资源，数量等同于你本回合已执行的行动数量（包括本行动）。
如果此时是你的回合，则结束你的回合。

简化说明：
- "本回合已执行的行动数"：引擎无逐回合行动计数（引擎缺口），近似为
  (3 - 剩余行动数) + 1（打出本卡也是一个行动；CARD_PLAYED 时本行动的
  行动点尚未扣除）。额外行动（Leo 等）会使该近似偏低，可由
  ctx.extra["actions_this_turn"] 显式指定真实值。
- "结束你的回合"：将 actions_remaining 置 0（调查阶段行动循环随之结束）；
  非自己回合打出（如快速窗口）时仅获得资源。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class PayDay(CardImplementation):
    card_id = "pay_day_lv1"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def gain_and_end_turn(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        actions_done = ctx.extra.get("actions_this_turn")
        if actions_done is None:
            actions_done = max(0, 3 - inv.actions_remaining) + 1
        inv.resources += actions_done
        ctx.extra["pay_day_gained"] = actions_done
        ctx.game_state.log_effect(f"💰 发薪日：本回合已行动{actions_done}次，获得{actions_done}资源")
        if inv.actions_remaining > 0:
            inv.actions_remaining = 0
            ctx.extra["pay_day_ended_turn"] = True
            ctx.game_state.log_effect("💰 发薪日：回合结束")
