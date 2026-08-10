"""Finn's Trusty .38 (Level 0) — Neutral Asset, Hand slot. Finn Edwards 专属。
快速。使用（3弹药）。
[action] 花费1弹药：战斗。本次攻击+2[combat]。若被攻击的敌人未与你交战，
本次攻击造成+1伤害。

简化说明：
- "花费1弹药"在 FIGHT_ACTION_INITIATED（以本武器发起攻击）时扣除，
  未命中同样消耗（同 rolands_38_special）。
- 0弹药时不扣弹药、不提供加值（等同徒手攻击；会话层应过滤武器可选项）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class FinnsTrusty38(CardImplementation):
    card_id = "finns_trusty_38_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._attack_paid = False
        self._target_engaged = True

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def pay_ammo_on_attack(self, ctx):
        self._attack_paid = False
        self._target_engaged = True
        if ctx.source != self.instance_id:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None or card.uses.get("ammo", 0) <= 0:
            return
        card.uses["ammo"] -= 1
        self._attack_paid = True
        # 记录目标是否与攻击者交战（影响+1伤害）
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and ctx.enemy_id is not None:
            self._target_engaged = ctx.enemy_id in inv.threat_area

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """+2 Combat for the attack paid for with this weapon."""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        ctx.modify_amount(2, "finns_trusty_38_combat_bonus")

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def extra_damage(self, ctx):
        """+1 damage if the attacked enemy is not engaged with you."""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if not self._target_engaged:
            ctx.modify_amount(1, "finns_trusty_38_extra_damage")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_attack_flag(self, ctx):
        self._attack_paid = False
        self._target_engaged = True
