""".45 Automatic (Level 0) — Guardian Asset, Hand slot.
Uses (4 ammo). 消耗1弹药：战斗时+1战斗力，成功时+1伤害。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class FortyFiveAutomatic(CardImplementation):
    card_id = "45_automatic_lv0"

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def combat_bonus(self, ctx):
        """+1 Combat when fighting with this weapon."""
        if ctx.source != self.instance_id:
            return
        if ctx.skill_type == Skill.COMBAT:
            ctx.modify_amount(1, "45_auto_combat_bonus")

    @on_event(
        GameEvent.DAMAGE_DEALT,
        priority=TimingPriority.WHEN,
    )
    def extra_damage(self, ctx):
        """+1 damage when attacking with this weapon."""
        if ctx.source != self.instance_id:
            return
        # Spend 1 ammo (already spent when initiating attack)
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card and card.uses.get("ammo", 0) > 0:
            card.uses["ammo"] -= 1
            ctx.modify_amount(1, "45_auto_extra_damage")
