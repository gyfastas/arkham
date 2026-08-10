"""Fortune or Fate (Level 2) — Survivor Event.
快速。在毁灭标记将被放置到任何一张冒险卡上时打出。
每场游戏最多1次。
取消刚要被放置到该卡牌上的1个毁灭标记。放逐幸运或是注定。

简化说明：
- 从手牌自动打出（persistent_in_hand）：DOOM_PLACED 时若资源足够且本场
  游戏尚未打出过，自动支付2资源打出并放逐（exiled_cards，引擎无放逐区）。
- 引擎的 DOOM_PLACED 在毁灭实际放置后才发出且无目标卡牌字段，取消实现为
  事后从密谋毁灭计数减1（净效果与官方一致）；放置到密谋以外卡牌上的毁灭
  无法定位（引擎缺口，见报告）。
- "每场游戏最多1次"记录在 scenario.vars["fortune_or_fate_used"]。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class FortuneOrFate(CardImplementation):
    card_id = "fortune_or_fate_lv2"
    persistent_in_hand = True  # 在手牌中持续监听毁灭放置窗口

    @on_event(GameEvent.DOOM_PLACED, priority=TimingPriority.WHEN)
    def cancel_doom(self, ctx):
        scenario = ctx.game_state.scenario
        if scenario.vars.get("fortune_or_fate_used"):
            return
        if (ctx.amount or 0) < 1 or scenario.doom_on_agenda < 1:
            return
        # 任意手持本卡且资源足够的调查员自动打出
        holder = None
        for inv in ctx.game_state.investigators.values():
            if self.card_id not in inv.hand:
                continue
            cd = ctx.game_state.get_card_data(self.card_id)
            cost = (getattr(cd, "cost", 2) or 2) if cd else 2
            if inv.resources >= cost:
                holder = (inv, cost)
                break
        if holder is None:
            return
        inv, cost = holder

        inv.resources -= cost
        inv.hand.remove(self.card_id)
        scenario.vars.setdefault("exiled_cards", []).append(self.card_id)
        scenario.vars["fortune_or_fate_used"] = True
        scenario.doom_on_agenda -= 1
        ctx.extra["fortune_or_fate_cancelled"] = True
        ctx.game_state.log_effect(
            "🃏 幸运或是注定：取消刚放置的1个毁灭标记，放逐本卡")
