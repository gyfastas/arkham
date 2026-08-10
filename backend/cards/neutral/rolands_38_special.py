"""罗兰的.38特种手枪（Roland's .38 Special）— 罗兰·班克斯专属支援卡，武器。
使用（4弹药）。
[行动]花费1弹药：战斗。该次攻击+1战斗（若你所在地点有1个或以上线索，
改为+3战斗），造成+1伤害。

简化说明：
- 卡面上"花费1弹药"是攻击动作的费用（无论命中与否），实现在
  FIGHT_ACTION_INITIATED（以本武器发起攻击）时扣除；未命中同样消耗。
- 0弹药时引擎仍允许以本武器发起攻击（FIGHT 行动不尊重事件取消，武器
  可选项需会话层过滤），此时不扣弹药、不提供任何加值，等同徒手攻击。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Rolands38Special(CardImplementation):
    card_id = "rolands_38_special"

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
        """+1 Combat (+3 instead if 1+ clues at your location) for the
        attack paid for with this weapon."""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        bonus = 1
        if inv is not None:
            location = ctx.game_state.get_location(inv.location_id)
            if location is not None and location.clues >= 1:
                bonus = 3
        ctx.modify_amount(bonus, "rolands_38_combat_bonus")

    @on_event(
        GameEvent.DAMAGE_DEALT,
        priority=TimingPriority.WHEN,
    )
    def extra_damage(self, ctx):
        """+1 damage for the attack paid for with this weapon."""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        ctx.modify_amount(1, "rolands_38_extra_damage")

    @on_event(
        GameEvent.SKILL_TEST_ENDS,
        priority=TimingPriority.AFTER,
    )
    def clear_attack_flag(self, ctx):
        self._attack_paid = False
