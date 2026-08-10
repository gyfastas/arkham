"""Sure Gamble (Level 3) — Rogue Event.
快速。在你揭示一个带有负修正的混沌标记后打出。将该标记的"-"翻成"+"。

简化说明：
- 自动触发：揭示负修正标记时，若手牌中有老千手法且资源足够支付费用，
  自动打出并翻转修正（官方为玩家选择打出时机；保持原有自动行为，
  翻转总是有利但会消耗2资源）。自动失败标记无数值修正，不触发。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class SureGamble(CardImplementation):
    card_id = "sure_gamble_lv3"

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def flip_token(self, ctx):
        # 仅负修正标记触发（auto_fail 无数值修正，天然排除，双重保险）
        if ctx.chaos_token == ChaosTokenType.AUTO_FAIL:
            return
        if ctx.amount >= 0:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or "sure_gamble_lv3" not in inv.hand:
            return
        cd = ctx.game_state.get_card_data("sure_gamble_lv3")
        cost = getattr(cd, "cost", None) if cd else None
        if cost is None:
            cost = 2
        if inv.resources < cost:
            return

        # 打出老千手法
        inv.resources -= cost
        inv.hand.remove("sure_gamble_lv3")
        inv.discard.append("sure_gamble_lv3")

        # 将该标记的"-"翻成"+"：-N → +N
        ctx.modify_amount(abs(ctx.amount) - ctx.amount, "sure_gamble_flip")
        ctx.extra["sure_gamble_flipped"] = True
