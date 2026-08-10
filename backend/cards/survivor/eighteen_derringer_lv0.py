""".18 Derringer (Level 0) — Survivor Asset, Hand slot.
Uses (2 ammo). [action] Spend 1 ammo: Fight. You get +2 [combat] and deal
+1 damage for this attack. If you fail, place 1 ammo on .18 Derringer.

简化说明：
- 弹药在发起攻击时（FIGHT_ACTION_INITIATED）扣除；失败时返还（不超过上限2）。
- 无弹药时官方禁止用本武器攻击；引擎 FIGHT_ACTION_INITIATED 无取消通道，
  近似为攻击继续但本武器不提供任何加值（引擎缺口，见修复报告）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class EighteenDerringer(CardImplementation):
    card_id = "18_derringer_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        # 本次攻击是否已支付弹药（无弹药时攻击不获得任何加值）
        self._attack_paid = False

    def _ammo_cap(self, ctx) -> int:
        cd = ctx.game_state.get_card_data(self.card_id)
        return (cd.uses or {}).get("ammo", 2) if cd else 2

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def spend_ammo(self, ctx):
        """花费1弹药：攻击。"""
        if ctx.source != self.instance_id:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None:
            return
        if card.uses.get("ammo", 0) < 1:
            self._attack_paid = False
            ctx.game_state.log_effect("🔫 .18大口径短口手枪：没有弹药，无法提供加值")
            return
        card.uses["ammo"] -= 1
        self._attack_paid = True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """+2 Combat when fighting with this weapon."""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if ctx.skill_type == Skill.COMBAT:
            ctx.modify_amount(2, "18_derringer_combat_bonus")

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def extra_damage(self, ctx):
        """+1 damage for this attack."""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        ctx.modify_amount(1, "18_derringer_extra_damage")

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.AFTER)
    def refund_ammo_on_fail(self, ctx):
        """If the attack fails, place 1 ammo back on the Derringer (上限2)。"""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is not None:
            card.uses["ammo"] = min(
                card.uses.get("ammo", 0) + 1, self._ammo_cap(ctx))

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_attack_state(self, ctx):
        if ctx.source == self.instance_id:
            self._attack_paid = False
