"""Fire Axe (Level 0) — Survivor Asset, Hand slot.
Fight action weapon. If you have 0 resources, +1 damage.
Free: During attack, spend 1 resource for +2 combat (limit 3 per attack).
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class FireAxe(CardImplementation):
    card_id = "fire_axe_lv0"

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def combat_bonus(self, ctx):
        """Weapon: +1 combat when fighting with Fire Axe."""
        from backend.models.enums import Skill
        if ctx.skill_type != Skill.COMBAT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            # Base weapon grants +1 combat
            ctx.modify_amount(1, "fire_axe_combat")
