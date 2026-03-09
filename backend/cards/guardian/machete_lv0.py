"""Machete (Level 0) — Guardian Asset, Hand slot.
战斗时+1战斗力。如果只与一个敌人交战，额外+1伤害。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Machete(CardImplementation):
    card_id = "machete_lv0"

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
        when=lambda ctx: (
            ctx.source is not None
            and ctx.extra.get("weapon_card_id") == "machete_lv0"
            or (ctx.source and ctx.game_state.get_card_instance(ctx.source)
                and ctx.game_state.get_card_instance(ctx.source).card_id == "machete_lv0")
        ),
    )
    def combat_bonus(self, ctx):
        """+1 Combat when fighting with this weapon."""
        if ctx.skill_type == Skill.COMBAT:
            ctx.modify_amount(1, "machete_combat_bonus")

    @on_event(
        GameEvent.DAMAGE_DEALT,
        priority=TimingPriority.WHEN,
    )
    def bonus_damage(self, ctx):
        """If engaged with only 1 enemy, +1 damage."""
        if ctx.source != self.instance_id:
            return
        inv_id = ctx.investigator_id
        if inv_id is None:
            return
        engaged = ctx.game_state.get_engaged_enemies(inv_id)
        if len(engaged) == 1:
            ctx.modify_amount(1, "machete_bonus_damage")
