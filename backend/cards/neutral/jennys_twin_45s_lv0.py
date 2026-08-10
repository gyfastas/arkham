"""珍妮的.45双枪（Jenny's Twin .45s，Level 0）— 珍妮·巴恩斯专属支援卡，武器（双手）。
使用（X弹药，按FAQ X=4）。
[行动]花费1弹药：攻击。该次攻击+2战斗，造成+1伤害。

简化说明：
- 卡面上"花费1弹药"是攻击动作的费用（无论命中与否），实现在
  FIGHT_ACTION_INITIATED（以本武器发起攻击）时扣除；未命中同样消耗。
- 0弹药时引擎仍允许以本武器发起攻击（FIGHT 行动不尊重事件取消，武器
  可选项需会话层过滤），此时不扣弹药、不提供任何加值，等同徒手攻击。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class JennysTwin45s(CardImplementation):
    card_id = "jennys_twin_45s_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._attack_paid = False  # 本次攻击已付1弹药

    @on_event(
        GameEvent.FIGHT_ACTION_INITIATED,
        priority=TimingPriority.WHEN,
    )
    def pay_ammo_on_attack(self, ctx):
        """Spend 1 ammo as the cost of attacking with this weapon."""
        self._attack_paid = False
        if ctx.source != self.instance_id:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None or card.uses.get("ammo", 0) <= 0:
            return
        card.uses["ammo"] -= 1
        self._attack_paid = True

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def combat_bonus(self, ctx):
        """+2 Combat for the attack paid for with this weapon."""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        ctx.modify_amount(2, "jennys_twin_45s_combat_bonus")

    @on_event(
        GameEvent.DAMAGE_DEALT,
        priority=TimingPriority.WHEN,
    )
    def extra_damage(self, ctx):
        """+1 damage for the attack paid for with this weapon."""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        ctx.modify_amount(1, "jennys_twin_45s_extra_damage")

    @on_event(
        GameEvent.SKILL_TEST_ENDS,
        priority=TimingPriority.AFTER,
    )
    def clear_attack_flag(self, ctx):
        self._attack_paid = False
