"""Until the End of Time (Level 0) — Neutral Asset. 卡尔文·怀特专属。
直接伤害和直接恐惧可以分配到时间尽头。（2生命/2理智承伤池）

简化说明：
- 引擎的 deal_damage(direct=True, target_instance_id=...) 通道本身不校验
  "直接伤害能否分配到支援卡"（官方默认不可，需卡面许可），故本卡无需解除
  限制；can_assign_direct() 显式表达该许可，供会话层构建分配选项时查询
  （引擎缺口：直接分配许可无通用校验钩子）。
- assign_direct() 提供带承伤上限与击败结算的直接分配实现（供会话层调用；
  击败离场镜像 DamageEngine 的移除流程，经 _shared.defeat_asset）。
"""

from backend.cards._shared import defeat_asset
from backend.cards.base import CardImplementation


class UntilTheEndOfTime(CardImplementation):
    card_id = "until_the_end_of_time_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def can_assign_direct(self, game_state, investigator_id) -> bool:
        """本卡在场且未达承伤上限时，直接伤害/恐惧可以分配给它。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None:
            return False
        return self.instance_id in inv.play_area

    def assign_direct(self, game_state, investigator_id,
                      damage: int = 0, horror: int = 0) -> bool:
        """将直接伤害/恐惧分配到本卡（受剩余生命/理智上限约束）。"""
        if not self.can_assign_direct(game_state, investigator_id):
            return False
        inst = game_state.get_card_instance(self.instance_id)
        cd = game_state.get_card_data(inst.card_id)
        applied = False
        if damage > 0 and cd is not None and cd.health is not None:
            actual = min(damage, max(0, cd.health - inst.damage))
            inst.damage += actual
            applied = applied or actual > 0
        if horror > 0 and cd is not None and cd.sanity is not None:
            actual = min(horror, max(0, cd.sanity - inst.horror))
            inst.horror += actual
            applied = applied or actual > 0
        if not applied:
            return False

        # 承伤池耗尽：本卡被击败离场
        defeated = False
        if cd is not None:
            if cd.health is not None and inst.damage >= cd.health:
                defeated = True
            if cd.sanity is not None and inst.horror >= cd.sanity:
                defeated = True
        if defeated:
            defeat_asset(game_state, self._bus, self.instance_id)
        return True
