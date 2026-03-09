"""Art Student (Level 0) — Seeker Asset, Ally slot.
进场时在你所在地点发现1条线索。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ArtStudent(CardImplementation):
    card_id = "art_student_lv0"

    @on_event(
        GameEvent.CARD_ENTERS_PLAY,
        priority=TimingPriority.REACTION,
    )
    def discover_clue_on_enter(self, ctx):
        """When Art Student enters play, discover 1 clue at your location."""
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        location = ctx.game_state.get_location(inv.location_id)
        if location and location.clues > 0:
            location.clues -= 1
            inv.clues += 1
