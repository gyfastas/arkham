"""Something Worth Fighting For (Level 0) — Guardian Asset. (05109)
理智3。
对你所在地点的其他调查员造成的恐惧可以分配到赴汤蹈火。

简化说明：
- 同地点其他调查员被分配恐惧时，自动由本卡承担（至多本卡剩余理智）。
  官方为"可以"（玩家逐点选择），自动承担为最有利/最常用分支的简化
  （与 true_grit 的伤害版同一模式）。
- 本卡承恐达到理智上限即被击败离场（镜像引擎离场流程）。
"""

from backend.cards._shared import defeat_asset
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class SomethingWorthFightingFor(CardImplementation):
    card_id = "something_worth_fighting_for_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def _holder(self, game_state):
        for inv in game_state.investigators.values():
            if self.instance_id in inv.play_area:
                return inv
        return None

    @on_event(GameEvent.HORROR_ASSIGNED, priority=TimingPriority.WHEN)
    def soak_for_others(self, ctx):
        """同地点其他调查员被分配恐惧时：自动由本卡承担。"""
        holder = self._holder(ctx.game_state)
        if holder is None:
            return
        target = ctx.game_state.get_investigator(ctx.investigator_id)
        if target is None or target.investigator_id == holder.investigator_id:
            return
        if target.location_id != holder.location_id:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        data = ctx.game_state.get_card_data(inst.card_id) if inst else None
        if inst is None or data is None or data.sanity is None:
            return
        remaining = data.sanity - inst.horror
        amount = min(remaining, ctx.amount or 0)
        if amount <= 0:
            return
        inst.horror += amount
        ctx.modify_amount(-amount, "something_worth_fighting_for_soak")
        ctx.game_state.log_effect(
            f"🔥 赴汤蹈火：代为承担{amount}点恐惧（{target.investigator_id}）")
        if inst.horror >= data.sanity:
            defeat_asset(ctx.game_state, self._bus, self.instance_id)
            ctx.game_state.log_effect("🔥 赴汤蹈火：恐惧达到上限，被击败")
