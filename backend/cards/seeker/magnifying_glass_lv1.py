"""Magnifying Glass (Level 1) — Seeker Asset, Hand slot. Fast.
快速打出。调查时+1智力。当你所在地点没有线索时，可以将此卡收回手牌。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class MagnifyingGlassLv1(CardImplementation):
    card_id = "magnifying_glass_lv1"

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def intellect_bonus(self, ctx):
        """+1 Intellect while investigating."""
        if ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "magnifying_glass_lv1_bonus")

    @on_event(
        GameEvent.CLUE_DISCOVERED,
        priority=TimingPriority.AFTER,
    )
    def check_return_to_hand(self, ctx):
        """After a clue is discovered, check if location has 0 clues remaining.

        If so, the player may return Magnifying Glass to hand.
        For now, auto-return when location is empty.
        """
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if self.instance_id not in inv.play_area:
            return
        location = ctx.game_state.get_location(inv.location_id)
        if location and location.clues == 0:
            # Return to hand
            inv.play_area.remove(self.instance_id)
            inv.hand.append(self.instance_id)
