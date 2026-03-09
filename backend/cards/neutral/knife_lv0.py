"""Knife (Level 0) — Neutral Asset, Hand slot.
刀子。战斗+1。弃置：战斗+2、伤害+1。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Knife(CardImplementation):
    card_id = "knife_lv0"

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def combat_bonus(self, ctx):
        """+1 Combat when fighting with this weapon."""
        if ctx.skill_type == Skill.COMBAT:
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv and self.instance_id in inv.play_area:
                ctx.modify_amount(1, "knife_bonus")
