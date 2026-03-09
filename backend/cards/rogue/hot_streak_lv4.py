"""Hot Streak (Level 4) — Rogue Event.
百战百胜。获得10资源。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class HotStreak(CardImplementation):
    card_id = "hot_streak_lv4"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def gain_resources(self, ctx):
        """Gain 10 resources when this card is played."""
        if ctx.extra.get("card_id") != "hot_streak_lv4":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv:
            inv.resources += 10
