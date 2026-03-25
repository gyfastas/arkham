"""Zoey's Cross — Signature Asset.
[reaction]在一名敌人与你交战后，消耗佐伊的十字架并花费1资源：对该敌人造成1点伤害。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ZoeysCross(CardImplementation):
    card_id = "zoeys_cross_lv0"

    @on_event(
        GameEvent.ENEMY_ENGAGED,
        priority=TimingPriority.REACTION,
    )
    def deal_damage_on_engage(self, ctx):
        """Reaction: After an enemy engages, exhaust and spend 1 resource to deal 1 damage."""
        # Check this event is for the controller of this card
        if ctx.investigator_id is None:
            return

        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # Check this card is in play for this investigator
        # Find the card instance
        cross_instance = None
        for inst_id in inv.play_area:
            inst = ctx.game_state.get_card_instance(inst_id)
            if inst and inst.card_id == "zoeys_cross_lv0":
                cross_instance = inst
                break

        if cross_instance is None:
            return

        # Check if already exhausted
        if cross_instance.exhausted:
            return

        # Check if has enough resources
        if inv.resources < 1:
            return

        # Get the enemy
        enemy_id = getattr(ctx, 'enemy_id', None)
        if enemy_id is None:
            enemy_id = ctx.extra.get('enemy_id')
        if enemy_id is None:
            return

        enemy = ctx.game_state.get_card_instance(enemy_id)
        if enemy is None:
            return

        enemy_data = ctx.game_state.get_card_data(enemy.card_id)
        if enemy_data is None or enemy_data.type_str != "enemy":
            return

        # Store pending choice for frontend
        # The actual execution will be handled when player confirms
        ctx.extra["zoey_cross_pending"] = {
            "card_instance_id": cross_instance.instance_id,
            "enemy_id": enemy_id,
            "investigator_id": ctx.investigator_id,
        }

    def activate(self, game_state, investigator_id):
        """Called when player chooses to activate the cross."""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False

        # Find the cross in play area
        cross_instance = None
        for inst_id in inv.play_area:
            inst = game_state.get_card_instance(inst_id)
            if inst and inst.card_id == "zoeys_cross_lv0":
                cross_instance = inst
                break

        if cross_instance is None or cross_instance.exhausted:
            return False

        if inv.resources < 1:
            return False

        # Get engaged enemies
        engaged_enemies = []
        for enemy_id in inv.threat_area:
            enemy = game_state.get_card_instance(enemy_id)
            if enemy:
                enemy_data = game_state.get_card_data(enemy.card_id)
                if enemy_data and enemy_data.type_str == "enemy":
                    engaged_enemies.append(enemy)

        if not engaged_enemies:
            return False

        # Deal damage to the most recently engaged enemy (last in threat_area)
        target_enemy = engaged_enemies[-1]

        # Pay cost
        inv.resources -= 1
        cross_instance.exhausted = True

        # Deal damage
        target_enemy.damage += 1

        return True
