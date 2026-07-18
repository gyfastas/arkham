"""Opportunist (Level 0) — Rogue Skill.
如果你成功，返回机会主义者到你的手中。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Opportunist(CardImplementation):
    card_id = "opportunist_lv0"

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def return_to_hand(self, ctx):
        if "opportunist_lv0" not in ctx.committed_cards:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "opportunist_lv0" in inv.discard:
            inv.discard.remove("opportunist_lv0")
            inv.hand.append("opportunist_lv0")
            ctx.extra["opportunist_returned"] = True
