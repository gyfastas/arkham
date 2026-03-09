"""You Handle This One! (Level 0) — Rogue Event.
Fast. 当你抽到非危难遭遇卡后，选择另一位调查员。该调查员被视为抽到该卡。获得1资源。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class YouHandleThisOne(CardImplementation):
    card_id = "you_handle_this_one_lv0"

    @on_event(
        GameEvent.ENCOUNTER_CARD_DRAWN,
        priority=TimingPriority.REACTION,
    )
    def redirect_encounter(self, ctx):
        """After drawing a non-peril encounter card, redirect it to another investigator.

        In single-player this has limited use, but the event bus hook is registered.
        The actual redirect logic requires a target selection UI, so this implementation
        focuses on the resource gain when triggered.

        Full implementation would:
        1. Check ctx.extra for "peril" keyword (skip if peril)
        2. Prompt player to choose another investigator
        3. Set ctx.extra["redirect_to"] = target_id
        4. Grant 1 resource to the playing investigator
        """
        pass  # Requires multi-player + UI interaction; skeleton for now

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.AFTER,
    )
    def gain_resource(self, ctx):
        """Gain 1 resource when this card is played."""
        if ctx.extra.get("card_id") != "you_handle_this_one_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv:
            inv.resources += 1
