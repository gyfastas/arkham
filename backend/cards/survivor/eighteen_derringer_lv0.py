""".18 Derringer (Level 0) — Survivor Asset, Hand slot.
Uses (2 ammo). 消耗1弹药：战斗时+2战斗力，成功时+1伤害。失败时放回1弹药。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class EighteenDerringer(CardImplementation):
    card_id = "18_derringer_lv0"

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def combat_bonus(self, ctx):
        """+2 Combat when fighting with this weapon."""
        if ctx.source != self.instance_id:
            return
        if ctx.skill_type == Skill.COMBAT:
            ctx.modify_amount(2, "18_derringer_combat_bonus")

    @on_event(
        GameEvent.DAMAGE_DEALT,
        priority=TimingPriority.WHEN,
    )
    def extra_damage(self, ctx):
        """+1 damage when attacking with this weapon, spending 1 ammo."""
        if ctx.source != self.instance_id:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card and card.uses.get("ammo", 0) > 0:
            card.uses["ammo"] -= 1
            ctx.modify_amount(1, "18_derringer_extra_damage")

    @on_event(
        GameEvent.SKILL_TEST_FAILED,
        priority=TimingPriority.AFTER,
    )
    def refund_ammo_on_fail(self, ctx):
        """If the attack fails, place 1 ammo back on the Derringer."""
        if ctx.source != self.instance_id:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card:
            card.uses["ammo"] = card.uses.get("ammo", 0) + 1
