"""Zoey Samaras — Guardian Investigator.
能力：[reaction]在你与一名敌人交战后：获得1个资源。
远古印记：+1。如果攻击中的这次技能检定成功，这次攻击造成+1伤害。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ZoeySamaras(CardImplementation):
    card_id = "zoey_samaras"

    @on_event(
        GameEvent.ENEMY_ENGAGED,
        priority=TimingPriority.REACTION,
    )
    def gain_resource_on_engage(self, ctx):
        """Reaction: After you become engaged with an enemy, gain 1 resource."""
        # Check this event is for the current investigator
        if ctx.investigator_id is None:
            return

        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # Check this is Zoey's investigator
        card_data = getattr(inv, 'card_data', None)
        if card_data is None:
            return
        if card_data.id != "zoey_samaras":
            return

        # Gain 1 resource
        inv.resources += 1

    @on_event(
        GameEvent.CHAOS_TOKEN_RESOLVED,
        priority=TimingPriority.WHEN,
    )
    def elder_sign_effect(self, ctx):
        """Elder Sign: +1. If successful during an attack, +1 damage."""
        if ctx.chaos_token is None:
            return
        from backend.models.enums import ChaosTokenType
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return

        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        card_data = getattr(inv, 'card_data', None)
        if card_data is None or card_data.id != "zoey_samaras":
            return

        # +1 modifier for the skill test
        ctx.modify_amount(1, "zoey_elder_sign")

        # Mark that this is an attack test for the success handler
        ctx.extra["zoey_elder_sign_attack"] = True

    @on_event(
        GameEvent.SKILL_TEST_SUCCESSFUL,
        priority=TimingPriority.AFTER,
    )
    def elder_sign_damage_bonus(self, ctx):
        """If elder sign and this was an attack, deal +1 damage."""
        is_attack = ctx.extra.get("zoey_elder_sign_attack", False)
        if not is_attack:
            return

        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        card_data = getattr(inv, 'card_data', None)
        if card_data is None or card_data.id != "zoey_samaras":
            return

        # Check if there's an enemy being attacked
        enemy_id = getattr(ctx, 'enemy_id', None) or ctx.extra.get('enemy_id')
        if enemy_id is None:
            return

        enemy = ctx.game_state.get_card_instance(enemy_id)
        if enemy is None:
            return

        enemy_data = ctx.game_state.get_card_data(enemy.card_id)
        if enemy_data is None or enemy_data.type_str != "enemy":
            return

        # Deal +1 damage to the enemy
        enemy.damage += 1
