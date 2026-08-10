"""Hand of Fate (Level 0) — Guardian Event. (07020)
快速。在一个敌人攻击你所在地点的调查员时打出。
取消该次攻击。然后，向混乱袋中加入等同于攻击敌人伤害值与恐惧值
合计数量的[祝福]标记。

简化说明：
- 从手牌中自动触发（官方为玩家选择时机）：敌人攻击持有者同地点的
  调查员（含持有者本人）时，若手牌中有本卡且资源足够，自动打出，
  同 heroic_rescue 的自动打出约定。
- 混沌袋经 bind_chaos_bag() 注入（registry.activate_card 自动接线）；
  未绑定时祝福标记不加入，攻击仍被取消（注明）。
"""

from backend.cards._shared import find_holder
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class HandOfFate(CardImplementation):
    card_id = "hand_of_fate_lv0"
    persistent_in_hand = True  # 手牌中持续监听敌人攻击

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bag = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._bag = chaos_bag

    @on_event(GameEvent.ENEMY_ATTACKS, priority=TimingPriority.WHEN)
    def cancel_attack(self, ctx):
        """敌人攻击同地点调查员：取消攻击，加祝福标记。"""
        target = ctx.game_state.get_investigator(ctx.investigator_id)
        if target is None:
            return
        holder = find_holder(ctx.game_state, self.card_id)
        if holder is None:
            return
        if holder.location_id != target.location_id:
            return
        enemy = ctx.game_state.get_card_instance(ctx.enemy_id) if ctx.enemy_id else None
        enemy_data = ctx.game_state.get_card_data(enemy.card_id) if enemy else None
        if enemy_data is None:
            return
        data = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(data, "cost", 3) or 3) if data else 3
        if holder.resources < cost:
            return

        # 从手牌打出（支付费用）
        holder.resources -= cost
        holder.hand.remove(self.card_id)
        holder.discard.append(self.card_id)

        # 取消该次攻击
        ctx.cancel()

        # 加入祝福标记 = 伤害值 + 恐惧值
        count = (enemy_data.enemy_damage or 0) + (enemy_data.enemy_horror or 0)
        if self._bag is not None:
            for _ in range(count):
                self._bag.add_token(ChaosTokenType.BLESS)
        ctx.extra["hand_of_fate_bless"] = count
        ctx.game_state.log_effect(
            f"✋ 命运之手：取消【{ctx.game_state.card_name(enemy.card_id)}】的攻击，"
            f"向混乱袋加入{count}个祝福标记")
