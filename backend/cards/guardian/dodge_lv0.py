"""Dodge (Level 0) — Guardian Event.
快速。在你所在地点的敌人攻击时打出。取消本次攻击。

简化说明：
- 从手牌中自动触发（"快速"反应的完整实现需要玩家确认时机）：
  敌人在敌人阶段攻击你时，若手牌中有闪躲，自动打出并取消该次攻击。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Dodge(CardImplementation):
    card_id = "dodge_lv0"

    @on_event(GameEvent.ENEMY_ATTACKS, priority=TimingPriority.WHEN)
    def cancel_attack(self, ctx):
        """敌人攻击你时：从手牌打出闪躲取消本次攻击。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "dodge_lv0" not in inv.hand:
            return
        # 从手牌打出（支付费用）
        cost = 1
        cd = ctx.game_state.get_card_data("dodge_lv0")
        if cd is not None and getattr(cd, "cost", None) is not None:
            cost = cd.cost
        if inv.resources < cost:
            return
        inv.resources -= cost
        inv.hand.remove("dodge_lv0")
        inv.discard.append("dodge_lv0")
        ctx.cancel()
        ctx.extra["dodge_cancelled_attack"] = True
