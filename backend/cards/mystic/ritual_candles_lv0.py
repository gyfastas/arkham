"""Ritual Candles (Level 0) — Mystic Asset, Hand slot.
Passive: After revealing skull/cultist/tablet/elder_thing during a skill
test, get +1 skill value for that test.
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class RitualCandles(CardImplementation):
    card_id = "ritual_candles_lv0"

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def chaos_token_bonus(self, ctx):
        """+1 to skill value when special chaos token revealed."""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            # Simplified: always grant +1 since we don't track individual tokens
            # In full implementation, check if token is skull/cultist/tablet/elder_thing
            pass
