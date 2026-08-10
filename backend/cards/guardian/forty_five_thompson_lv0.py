""".45 Thompson (Level 0) — Guardian Asset, Hand x2. (05184)
使用(5弹药)。[行动]花费1弹药：攻击。本次攻击你获得+2战斗、造成+1伤害。

实现说明：
- 弹药在 FIGHT_ACTION_INITIATED（以本武器发起攻击）时支付（与 .45自动手枪
  lv2 一致；未命中同样消耗）；无弹药时取消攻击。
- lv3 子类覆盖 _on_ammo_spent：花费的弹药放入资源池。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class FortyFiveThompsonLv0(CardImplementation):
    card_id = "45_thompson_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._attack_paid = False

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def pay_ammo(self, ctx):
        """发起攻击时花费1弹药；无弹药则无法以本武器攻击。"""
        self._attack_paid = False
        if ctx.source != self.instance_id:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None or card.uses.get("ammo", 0) <= 0:
            ctx.cancel()
            ctx.game_state.log_effect("🔫 .45汤姆逊冲锋枪：没有弹药，无法攻击")
            return
        card.uses["ammo"] -= 1
        self._attack_paid = True
        self._on_ammo_spent(ctx, 1)

    def _on_ammo_spent(self, ctx, amount: int) -> None:
        """Hook for subclasses（lv3：花费的弹药转化为资源）。"""

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """已付弹药的攻击 +2 战斗。"""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if ctx.skill_type == Skill.COMBAT:
            ctx.modify_amount(2, "45_thompson_combat_bonus")

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def extra_damage(self, ctx):
        """已付弹药的攻击造成 +1 伤害。"""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        ctx.modify_amount(1, "45_thompson_extra_damage")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._attack_paid = False
