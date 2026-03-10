"""Daisy Walker — Seeker Investigator.
能力：每回合可执行1个额外行动，只能用于启动典籍(Tome)能力。
远古印记：+0，成功时每控制1个典籍抽1张牌。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class DaisyWalker(CardImplementation):
    card_id = "daisy_walker"

    @on_event(
        GameEvent.INVESTIGATION_PHASE_BEGINS,
        priority=TimingPriority.WHEN,
    )
    def grant_tome_action(self, ctx):
        """Grant Daisy 1 extra TOME action at the start of investigation phase.

        This bonus action can only be used for Tome abilities.
        The Tome-only restriction is enforced by checking card traits.
        """
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        # Check this is Daisy's investigator
        if inv.card_data.id != "daisy_walker":
            return
        # Grant 1 tome-specific action
        inv.tome_actions_remaining += 1

    @on_event(
        GameEvent.CHAOS_TOKEN_RESOLVED,
        priority=TimingPriority.WHEN,
    )
    def elder_sign_effect(self, ctx):
        """Elder Sign: +0. If successful, draw 1 card per Tome controlled."""
        if ctx.chaos_token is None:
            return
        from backend.models.enums import ChaosTokenType
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or inv.card_data.id != "daisy_walker":
            return
        # +0 modifier (already default)
        # Count tomes — draw happens on success, but we note the count here
        # Actual draw is handled in SKILL_TEST_SUCCESSFUL
        tome_count = 0
        for inst_id in inv.play_area:
            ci = ctx.game_state.get_card_instance(inst_id)
            if ci:
                cd = ctx.game_state.get_card_data(ci.card_id)
                if cd and "tome" in cd.traits:
                    tome_count += 1
        # Store for later use in success handler
        ctx.extra["daisy_elder_sign_tomes"] = tome_count

    @on_event(
        GameEvent.SKILL_TEST_SUCCESSFUL,
        priority=TimingPriority.AFTER,
    )
    def elder_sign_draw(self, ctx):
        """If elder sign triggered, draw cards equal to Tome count."""
        tome_count = getattr(ctx, '_extra', {}).get("daisy_elder_sign_tomes", 0)
        if not tome_count:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv:
            for _ in range(tome_count):
                if inv.deck:
                    inv.hand.append(inv.deck.pop(0))
