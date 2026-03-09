"""Holy Rosary (Level 0) — Mystic Asset, Accessory slot.
+1意志力。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class HolyRosary(CardImplementation):
    card_id = "holy_rosary_lv0"

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def willpower_bonus(self, ctx):
        """+1 Willpower while in play."""
        if ctx.skill_type == Skill.WILLPOWER:
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv and self.instance_id in inv.play_area:
                ctx.modify_amount(1, "holy_rosary_bonus")
