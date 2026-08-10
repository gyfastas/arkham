"""Faustian Bargain (Level 0) — Rogue Event. (07028)
作为打出浮士德的交易的额外费用，向混沌袋加入2个[curse]标记。
你所在地点的调查员们合计获得5资源，由你任意分配。

简化说明：
- "任意分配"需玩家选择；简化为全部由打出者获得（单人局即官方行为；
  多人局分配选择需会话层 UI，列为简化）。
- 混沌袋经 bind_chaos_bag() 注入（registry.activate_card 自动接线）；
  [curse]标记按官方规则上限10个封顶（同 promise_of_power）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

_MAX_CURSE_TOKENS = 10


class FaustianBargain(CardImplementation):
    card_id = "faustian_bargain_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.AFTER)
    def resolve(self, ctx):
        if ctx.extra.get("card_id") != "faustian_bargain_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # 额外费用：向混沌袋加入2个[curse]标记（封顶10个）
        added = 0
        if self._chaos_bag is not None:
            existing = sum(1 for t in self._chaos_bag.tokens + self._chaos_bag.sealed
                           if t == ChaosTokenType.CURSE)
            for _ in range(min(2, max(0, _MAX_CURSE_TOKENS - existing))):
                self._chaos_bag.add_token(ChaosTokenType.CURSE)
                added += 1

        # 你所在地点的调查员合计获得5资源（简化：全给打出者）
        inv.resources += 5
        ctx.extra["faustian_bargain_curses"] = added
        ctx.extra["faustian_bargain_resources"] = 5
        ctx.game_state.log_effect(
            f"😈 浮士德的交易：混沌袋加入{added}个[curse]，获得5资源")
