"""Stirring Up Trouble (Level 1) — Seeker Event. (07112)
作为打出掀起麻烦的额外费用，加入数量等于你所在地点隐藏值的[curse]
标记到混乱袋。
发现你所在地点的2个线索。

说明：
- 混沌袋由 registry.activate_card 注入（bind_chaos_bag）；测试中需手动
  bind_chaos_bag；
- 诅咒标记为额外费用，即使地点没有线索也会加入（官方：费用在打出时
  支付，与效果无关）；线索不足2个时按实际数量发现。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class StirringUpTrouble(CardImplementation):
    card_id = "stirring_up_trouble_lv1"

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def resolve(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        location = ctx.game_state.get_location(inv.location_id)

        # 额外费用：加入等同于隐藏值的诅咒标记
        bag = getattr(self, "_chaos_bag", None)
        shroud = location.shroud if location is not None else 0
        if bag is not None and shroud > 0:
            for _ in range(shroud):
                bag.add_token(ChaosTokenType.CURSE)
            ctx.extra["stirring_up_trouble_curses"] = shroud

        # 发现2个线索
        if location is not None and location.clues > 0:
            found = min(2, location.clues)
            location.clues -= found
            inv.clues += found
            ctx.extra["stirring_up_trouble_clues"] = found
            ctx.game_state.log_effect(
                f"😈 掀起麻烦：加入{shroud}个诅咒标记，发现{found}个线索")
        elif bag is not None and shroud > 0:
            ctx.game_state.log_effect(f"😈 掀起麻烦：加入{shroud}个诅咒标记")
