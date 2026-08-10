"""Becky (Level 0) — Neutral Asset, Weapon (Tommy Muldoon deck only).
使用（2弹药）。
汤米·马洛尼[reaction]能力获得的每个资源可以改为放置在贝基上，作为弹药。
[行动]花费1弹药：战斗。本次攻击+2[combat]，造成+1伤害。

简化说明：
- "花费1弹药"是攻击动作的费用（无论命中与否），实现在
  FIGHT_ACTION_INITIATED（以本武器发起攻击）时扣除（同 jennys_twin_45s_lv0）。
- 汤米的反应资源转为弹药：引擎无汤米·马洛尼调查员实现（缺口），提供
  place_resource_as_ammo() 供会话层在该反应结算时调用。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Becky(CardImplementation):
    card_id = "becky_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._attack_paid = False  # 本次攻击已付1弹药

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
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

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """+2 Combat for the attack paid for with this weapon."""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        ctx.modify_amount(2, "becky_combat_bonus")

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def extra_damage(self, ctx):
        """+1 damage for the attack paid for with this weapon."""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        ctx.modify_amount(1, "becky_extra_damage")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_attack_flag(self, ctx):
        self._attack_paid = False

    def place_resource_as_ammo(self, game_state, investigator_id) -> bool:
        """汤米反应获得的资源改为作为弹药放置在贝基上（会话层调用）。"""
        card = game_state.get_card_instance(self.instance_id)
        if card is None:
            return False
        card.uses["ammo"] = card.uses.get("ammo", 0) + 1
        game_state.log_effect("🔫 贝基：汤米反应的资源转为1弹药")
        return True
