"""Evidence! (Level 0) — Guardian Event.
快速。在你击败一个敌人后打出。发现你所在地点的1条线索。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Evidence(CardImplementation):
    card_id = "evidence_lv0"

    @on_event(
        GameEvent.ENEMY_DEFEATED,
        priority=TimingPriority.REACTION,
    )
    def discover_clue(self, ctx):
        """After defeating an enemy, discover 1 clue at your location."""
        if ctx.extra.get("card_id") != "evidence_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        location = ctx.game_state.get_location(inv.location_id)
        if location and location.clues > 0:
            location.clues -= 1
            inv.clues += 1
