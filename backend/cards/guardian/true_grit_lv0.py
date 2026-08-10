"""True Grit (Level 0) — Guardian Asset. (03021)
生命3。
你所在地点的其他调查员受到的伤害可以分配给勇气过人。

简化说明：
- 引擎 deal_damage 的 damage_assignment 参数本就不校验资产归属，会话层可
  直接把其他调查员的伤害分给本卡；这里实现自动分支：同地点其他调查员被
  分配伤害时，自动由本卡承担（至多本卡剩余生命）。官方为"可以"（玩家逐点
  选择），自动承担为最有利/最常用分支的简化。
- 本卡承伤达到生命上限即被击败离场（镜像引擎离场流程）。
"""

from backend.cards._shared import defeat_asset
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class TrueGrit(CardImplementation):
    card_id = "true_grit_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def _holder(self, game_state):
        """持有者：装备区含本卡的调查员。"""
        for inv in game_state.investigators.values():
            if self.instance_id in inv.play_area:
                return inv
        return None

    @on_event(GameEvent.DAMAGE_ASSIGNED, priority=TimingPriority.WHEN)
    def soak_for_others(self, ctx):
        """同地点其他调查员被分配伤害时：自动由本卡承担。"""
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
        if inst is None or data is None or data.health is None:
            return
        remaining = data.health - inst.damage
        amount = min(remaining, ctx.amount or 0)
        if amount <= 0:
            return
        inst.damage += amount
        ctx.modify_amount(-amount, "true_grit_soak")
        ctx.game_state.log_effect(
            f"💪 勇气过人：代为承担{amount}点伤害（{target.investigator_id}）")
        if inst.damage >= data.health:
            defeat_asset(ctx.game_state, self._bus, self.instance_id)
            ctx.game_state.log_effect("💪 勇气过人：伤害达到上限，被击败")
