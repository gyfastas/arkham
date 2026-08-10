"""Dodge (Level 2) — Guardian Event. (08026)
快速。当敌人攻击你所在地点的一名调查员时打出。
取消本次攻击。然后，检定敏捷(1)。如果成功，对该敌人造成1点伤害。

简化说明：
- 从手牌中自动触发（同 dodge_lv0 惯例）：敌人攻击你所在地点的调查员时，
  若你手牌中有本卡则自动打出（0费）并取消攻击。
- 敏捷(1)检定由卡牌实现手动结算（卡实现拿不到技能检定引擎）：从混沌袋
  抽1个标记（bind_chaos_bag 注入），敏捷+标记修正 ≥ 1 成功；自动失败
  标记视为失败。无投入卡/事件窗口——简化注明。
- 成功后的1点伤害经 _shared.deal_damage_to_enemy 结算（含击败流程）。
"""

from backend.cards._shared import deal_damage_to_enemy, find_holder
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CHAOS_TOKEN_VALUES, ChaosTokenType, GameEvent, Skill, TimingPriority,
)

_TEST_DIFFICULTY = 1


class DodgeLv2(CardImplementation):
    card_id = "dodge_lv2"
    persistent_in_hand = True  # 手牌中持续监听敌人攻击

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._chaos_bag = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.ENEMY_ATTACKS, priority=TimingPriority.WHEN)
    def cancel_attack(self, ctx):
        """敌人攻击你所在地点的调查员时：自动打出，取消攻击并反制。"""
        target_inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if target_inv is None:
            return
        holder = find_holder(ctx.game_state, self.card_id)
        if holder is None:
            return
        if holder.location_id != target_inv.location_id:
            return
        data = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(data, "cost", 0) or 0) if data else 0
        if holder.resources < cost:
            return

        # 从手牌打出（支付费用）并取消攻击
        holder.resources -= cost
        holder.hand.remove(self.card_id)
        holder.discard.append(self.card_id)
        ctx.cancel()
        ctx.extra["dodge_lv2_cancelled"] = True
        ctx.game_state.log_effect("🌀 闪躲(2)：取消敌人的攻击")

        # 敏捷(1)检定：成功则对该敌人造成1点伤害
        enemy_iid = ctx.enemy_id
        if enemy_iid is None:
            return
        agility = holder.get_skill(Skill.AGILITY)
        success = self._run_agility_test(agility)
        ctx.extra["dodge_lv2_test_success"] = success
        if success:
            deal_damage_to_enemy(ctx.game_state, self._bus, enemy_iid, 1,
                                 defeated_by=holder.investigator_id)
            ctx.game_state.log_effect("🌀 闪躲(2)：敏捷检定成功，反击1点伤害")

    def _run_agility_test(self, agility: int) -> bool:
        """手动敏捷检定(1)：抽1个混沌标记，敏捷+修正 ≥ 1。"""
        if self._chaos_bag is None:
            return agility >= _TEST_DIFFICULTY
        token = self._chaos_bag.draw()
        if token == ChaosTokenType.AUTO_FAIL:
            return False
        modifier = CHAOS_TOKEN_VALUES.get(token) or 0
        return agility + modifier >= _TEST_DIFFICULTY
