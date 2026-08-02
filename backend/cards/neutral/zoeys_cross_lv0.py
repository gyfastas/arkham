"""Zoey's Cross — Signature Asset.
[reaction]在一名敌人与你交战后，消耗佐伊的十字架并花费1资源：对该敌人造成1点伤害。

Note: This card's Reaction is now handled by Zoey's investigator ability
in zoey_samaras.py to provide a unified choice interface when engaging.
"""

from backend.cards.base import CardImplementation


class ZoeysCross(CardImplementation):
    card_id = "zoeys_cross_lv0"

    # Free combat ability. It is separate from the normal fight roll: the
    # player may activate it during a combat test without spending an action.
    activations = [{
        "id": "combat_damage",
        "label": "花费1资源：对一名交战敌人造成1伤害",
        "method": "activate_combat_damage",
        "target": "enemy",
        "actions": 0,
        "resource_cost": 1,
        "timing": "combat",
    }]

    def activate_combat_damage(self, game_state, investigator_id: str,
                               enemy_instance_id: str) -> bool:
        """Exhaust the Cross and spend one resource to damage an engaged enemy."""
        inv = game_state.get_investigator(investigator_id)
        cross = game_state.get_card_instance(self.instance_id)
        if inv is None or cross is None or cross.exhausted or inv.resources < 1:
            return False
        if enemy_instance_id not in inv.threat_area:
            return False
        enemy = game_state.get_card_instance(enemy_instance_id)
        if enemy is None:
            return False

        inv.resources -= 1
        cross.exhausted = True
        enemy.damage += 1
        return True

    # The reaction ability is handled by the ZoeySamaras class
    # to provide a unified choice interface when an enemy engages.
    # The actual effect execution is in game_session.py _resolve_choice
    # under the "zoey_reactions_on_engage" kind.
