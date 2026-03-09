"""Tests for Machete (Level 0)."""

import pytest
from backend.cards.guardian.machete_lv0 import Machete
from backend.engine.event_bus import EventBus, EventContext
from backend.engine.game import Game
from backend.models.enums import (
    Action, ChaosTokenType, GameEvent, PlayerClass, Skill, SlotType, TimingPriority,
)
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import make_enemy_data, make_investigator_data, make_location_data


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(combat=4)
    g.register_card_data(inv_data)

    loc = make_location_data()
    g.register_card_data(loc)

    machete_data = CardData(
        id="machete_lv0", name="Machete", name_cn="弯刀",
        type=__import__('backend.models.enums', fromlist=['CardType']).CardType.ASSET,
        card_class=PlayerClass.GUARDIAN, cost=3,
        slots=[SlotType.HAND], traits=["item", "weapon", "melee"],
        skill_icons={"combat": 1},
    )
    g.register_card_data(machete_data)

    enemy_data = make_enemy_data(fight=3, health=4)
    g.register_card_data(enemy_data)

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=2)

    # Register machete implementation
    g.card_registry.register_class(Machete)

    return g


def _equip_machete(game):
    """Play machete into inv1's play area."""
    inv = game.state.get_investigator("inv1")
    instance_id = game.state.next_instance_id()
    card_inst = CardInstance(
        instance_id=instance_id, card_id="machete_lv0",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND],
    )
    game.state.cards_in_play[instance_id] = card_inst
    inv.play_area.append(instance_id)
    game.card_registry.activate_card("machete_lv0", instance_id, game.event_bus)
    return instance_id


def _spawn_enemy(game, instance_id="enemy_1"):
    enemy = CardInstance(
        instance_id=instance_id, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    inv = game.state.get_investigator("inv1")
    inv.threat_area.append(instance_id)
    return enemy


class TestMachete:
    def test_card_registered(self, game):
        assert "machete_lv0" in game.card_registry.registered_cards

    def test_bonus_damage_single_enemy(self, game):
        """Machete deals +1 damage when engaged with only 1 enemy."""
        machete_id = _equip_machete(game)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1",
            weapon_instance_id=machete_id,
        )
        # Base 1 damage + 1 machete bonus = 2
        assert enemy.damage == 2

    def test_no_bonus_damage_multiple_enemies(self, game):
        """Machete does NOT deal bonus damage with 2+ enemies engaged."""
        machete_id = _equip_machete(game)
        enemy1 = _spawn_enemy(game, "enemy_1")
        enemy2 = _spawn_enemy(game, "enemy_2")
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1",
            weapon_instance_id=machete_id,
        )
        # Only base 1 damage, no machete bonus
        assert enemy1.damage == 1

    def test_combat_bonus(self, game):
        """Machete provides +1 combat during fight skill test."""
        machete_id = _equip_machete(game)
        _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        # Combat 4 + 1 machete = 5 vs fight 3 -> success
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1",
            weapon_instance_id=machete_id,
        )
        enemy = game.state.get_card_instance("enemy_1")
        assert enemy.damage > 0  # Succeeded and dealt damage
