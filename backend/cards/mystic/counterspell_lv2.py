"""Counterspell (Level 2) — Mystic Event. (04110)
快速。在你所在地点的技能检定期间揭示[skull]、[cultist]、[tablet]或
[elder_thing]混乱标记时打出。取消该混乱标记。（不要再揭示新标记替代。）

简化说明：
- 从手牌中自动触发（同 a_test_of_will 惯例）：你所在地点的检定揭示上述
  符号标记时，若你手牌中有反击法术且资源足够，自动打出（付2资源）。
- 取消实现：WHEN 优先级清零标记修正并将 ctx.chaos_token 置为 None，
  使后续（AFTER）的符号触发效果（如皱缩术受恐）不再响应；不补抽新标记
  （引擎本不重抽）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

_CANCELLABLE = {
    ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING,
}


class Counterspell(CardImplementation):
    card_id = "counterspell_lv2"
    persistent_in_hand = True  # 在手牌中持续监听标记揭示窗口

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._spent = False  # 已打出（本实例不再响应）

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def cancel_token(self, ctx):
        if self._spent or ctx.chaos_token not in _CANCELLABLE:
            return
        tester = ctx.game_state.get_investigator(ctx.investigator_id)
        if tester is None:
            return
        # 你所在地点：找与检定者同地点、手牌中有本卡的持有者
        holder = None
        for cand in ctx.game_state.investigators.values():
            if cand.location_id != tester.location_id:
                continue
            if self.card_id in cand.hand:
                holder = cand
                break
        if holder is None:
            return

        my_cd = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(my_cd, "cost", 2) or 2) if my_cd else 2
        if holder.resources < cost:
            return

        # 自动打出（简化：官方为玩家自行选择打出时机）
        holder.resources -= cost
        holder.hand.remove(self.card_id)
        holder.discard.append(self.card_id)
        self._spent = True

        # 取消标记：清零修正、抑制符号效果，不重抽
        token = ctx.chaos_token
        if ctx.amount:
            ctx.modify_amount(-ctx.amount, "counterspell_cancel")
        ctx.chaos_token = None
        ctx.extra["counterspell_cancelled"] = getattr(token, "value", str(token))
        ctx.game_state.log_effect(f"🪄 反击法术：取消混乱标记[{token.value}]")
