""""Hit me!" (Level 0) — Rogue Event. (08112)
快速。在你在技能检定中揭示一枚混沌标记后打出。
额外揭示1枚混沌标记，将其"-"转为"+"。若该标记为[skull]，你自动失败。

简化说明：
- 从手牌中自动触发（官方为玩家选择时机）：仅当原揭示标记的修正为负
  （落后，加注才有意义）且资源足够时自动打出。
- 额外标记的数值修正取绝对值（"-1"→"+1"，[curse]的-2→+2；非负标记
  不变；场景符号按0估值）；[skull]与[auto_fail]均导致自动失败
  （后者为标记固有效果），经 extra["force_auto_fail"] 通道。
- 混沌袋经 bind_chaos_bag() 注入；未绑定时不触发。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CHAOS_TOKEN_VALUES, ChaosTokenType, GameEvent, TimingPriority,
)


class HitMe(CardImplementation):
    card_id = "hit_me_lv0"
    persistent_in_hand = True  # 在手牌中持续监听标记揭示窗口

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def double_down(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return
        if self._chaos_bag is None:
            return
        # 自动打出策略（简化）：仅当前修正为负时才加注
        if (ctx.amount or 0) >= 0:
            return
        cd = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(cd, "cost", 1) or 1) if cd else 1
        if inv.resources < cost:
            return
        inv.resources -= cost
        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)

        token = self._chaos_bag.draw()
        value = CHAOS_TOKEN_VALUES.get(token) or 0
        flipped = -value if value < 0 else value  # "-"转为"+"
        ctx.modify_amount(flipped, "hit_me_extra_token")
        ctx.extra["hit_me_token"] = token.value
        if token in (ChaosTokenType.SKULL, ChaosTokenType.AUTO_FAIL):
            ctx.extra["force_auto_fail"] = True
            ctx.game_state.log_effect(
                f"🃏 打我！：额外揭示[{token.value}]，自动失败")
        else:
            ctx.game_state.log_effect(
                f"🃏 打我！：额外揭示[{token.value}]（视为+{flipped}）")
