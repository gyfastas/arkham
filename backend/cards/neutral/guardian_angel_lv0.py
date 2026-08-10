"""Guardian Angel (Level 0) — Neutral Asset. Sister Mary 专属。
守护天使可以被分配给你所在地点及相连地点的其他调查员受到的伤害。
[reaction] 当任意数量的伤害被分配给守护天使时：向混沌袋中加入等量的
[bless]标记。

简化说明：
- "分配给其他调查员的伤害"：引擎 DamageEngine 的承伤分配不按归属校验，
  可分配资格由会话层决定；本卡提供 can_soak_for() 供会话层查询
  （同地点或相连地点的其他调查员）。
- 分配伤害无引擎事件（_assign_damage 逐资产结算且无钩子），故反应实现为
  公开方法 assign_damage()：会话层在把伤害分配给本卡时调用，结算伤害并
  向混沌袋加入等量 [bless]（引擎缺口：资产承伤事件）。
- 混沌袋经 bind_chaos_bag() 注入（registry.activate_card 自动接线）。
"""

from backend.cards._shared import defeat_asset
from backend.cards.base import CardImplementation
from backend.models.enums import ChaosTokenType


class GuardianAngel(CardImplementation):
    card_id = "guardian_angel_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bag = None
        self._bus = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._bag = chaos_bag

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def can_soak_for(self, game_state, investigator_id) -> bool:
        """本卡是否可为指定调查员承伤（同地点/相连地点的其他调查员）。"""
        inst = game_state.get_card_instance(self.instance_id)
        owner = game_state.get_investigator(inst.controller_id) if inst else None
        target = game_state.get_investigator(investigator_id)
        if inst is None or owner is None or target is None:
            return False
        if investigator_id == owner.investigator_id:
            return True  # 持有者自身的承伤走引擎常规通道
        if target.location_id == owner.location_id:
            return True
        loc = game_state.get_location(owner.location_id)
        return loc is not None and target.location_id in loc.connections

    def assign_damage(self, game_state, amount: int) -> int:
        """将 amount 点伤害分配给守护天使；返回实际分配数。

        触发 [reaction]：向混沌袋加入等量 [bless] 标记。
        """
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or amount <= 0:
            return 0
        data = game_state.get_card_data(inst.card_id)
        remaining = (data.health or 0) - inst.damage if data else amount
        actual = max(0, min(amount, remaining))
        if actual <= 0:
            return 0
        inst.damage += actual
        if self._bag is not None:
            for _ in range(actual):
                self._bag.add_token(ChaosTokenType.BLESS)
        game_state.log_effect(
            f"😇 守护天使：被分配 {actual} 点伤害，"
            f"向混沌袋加入 {actual} 个[bless]标记"
        )
        if data is not None and data.health is not None \
                and inst.damage >= data.health:
            defeat_asset(game_state, self._bus, self.instance_id)
        return actual
