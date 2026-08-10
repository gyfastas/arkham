""".32 Colt (Level 0) — Guardian Asset, Hand slot. (03020)
使用(6子弹)。[行动]花费1子弹：攻击。本次攻击造成+1伤害。

实现说明：
- 弹药在 FIGHT_ACTION_INITIATED（以本武器发起攻击）时支付，与官方时机一致
  （未命中同样消耗），同 rolands_38_special。
- 无弹药时取消攻击（引擎尊重 FIGHT_ACTION_INITIATED 的取消，不消耗行动）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ThirtyTwoColt(CardImplementation):
    card_id = "32_colt_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._attack_paid = False  # 本次攻击已付1子弹

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def pay_ammo(self, ctx):
        """发起攻击时花费1子弹；无子弹则无法以本武器攻击。"""
        self._attack_paid = False
        if ctx.source != self.instance_id:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None or card.uses.get("ammo", 0) <= 0:
            ctx.cancel()
            ctx.game_state.log_effect("🔫 .32柯尔特：没有子弹，无法攻击")
            return
        card.uses["ammo"] -= 1
        self._attack_paid = True

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def extra_damage(self, ctx):
        """已付子弹的攻击造成 +1 伤害。"""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        ctx.modify_amount(1, "32_colt_extra_damage")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_flag(self, ctx):
        self._attack_paid = False
