"""Police Badge (Level 2) — Guardian Asset, Accessory slot.
+1意志力。弃置：一名调查员获得2个额外行动。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class PoliceBadge(CardImplementation):
    card_id = "police_badge_lv2"

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def willpower_bonus(self, ctx):
        """+1 Willpower while Police Badge is in play."""
        if ctx.skill_type == Skill.WILLPOWER:
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv and self.instance_id in inv.play_area:
                ctx.modify_amount(1, "police_badge_willpower_bonus")
