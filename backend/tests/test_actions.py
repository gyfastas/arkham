"""Tests for ActionResolver."""

import pytest
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, Skill
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_event_data,
    make_investigator_data, make_location_data,
)
from backend.models.state import CardInstance
from backend.models.enums import SlotType, PlayerClass


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(intellect=4, combat=4, agility=3)
    g.register_card_data(inv_data)

    loc1 = make_location_data(id="loc1", shroud=2, clue_value=3, connections=["loc2"])
    loc2 = make_location_data(id="loc2", shroud=3, clue_value=2, connections=["loc1"])
    g.register_card_data(loc1)
    g.register_card_data(loc2)

    g.add_investigator("inv1", inv_data, starting_location="loc1", deck=["card_a", "card_b", "card_c"])
    g.add_location("loc1", loc1, clues=3)
    g.add_location("loc2", loc2, clues=2)

    return g


class TestInvestigate:
    def test_investigate_success_discovers_clue(self, game):
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        game.action_resolver.perform_action("inv1", Action.INVESTIGATE)
        loc = game.state.get_location("loc1")
        # intellect 4 + 1 = 5 >= shroud 2 -> success
        assert inv.clues == 1
        assert loc.clues == 2

    def test_investigate_failure_no_clue(self, game):
        game.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        game.action_resolver.perform_action("inv1", Action.INVESTIGATE)
        assert inv.clues == 0


class TestMove:
    def test_move_to_connected_location(self, game):
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        result = game.action_resolver.perform_action("inv1", Action.MOVE, destination="loc2")
        assert result
        assert inv.location_id == "loc2"

    def test_cannot_move_to_unconnected(self, game):
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        result = game.action_resolver.perform_action("inv1", Action.MOVE, destination="nonexistent")
        assert not result


class TestDraw:
    def test_draw_adds_card_to_hand(self, game):
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        initial_hand = len(inv.hand)
        initial_deck = len(inv.deck)

        game.action_resolver.perform_action("inv1", Action.DRAW)
        assert len(inv.hand) == initial_hand + 1
        assert len(inv.deck) == initial_deck - 1


class TestResource:
    def test_resource_gains_one(self, game):
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        initial = inv.resources

        game.action_resolver.perform_action("inv1", Action.RESOURCE)
        assert inv.resources == initial + 1


class TestFight:
    def test_fight_success_deals_damage(self, game):
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]
        enemy_data = make_enemy_data(fight=3, health=3)
        game.register_card_data(enemy_data)

        enemy = CardInstance(
            instance_id="enemy_1", card_id="test_enemy",
            owner_id="scenario", controller_id="scenario",
        )
        game.state.cards_in_play["enemy_1"] = enemy
        inv = game.state.get_investigator("inv1")
        inv.threat_area.append("enemy_1")
        inv.actions_remaining = 3

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
        )
        assert enemy.damage == 1

    def test_fight_failure_no_damage(self, game):
        game.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]
        enemy_data = make_enemy_data(fight=3, health=3)
        game.register_card_data(enemy_data)

        enemy = CardInstance(
            instance_id="enemy_1", card_id="test_enemy",
            owner_id="scenario", controller_id="scenario",
        )
        game.state.cards_in_play["enemy_1"] = enemy
        inv = game.state.get_investigator("inv1")
        inv.threat_area.append("enemy_1")
        inv.actions_remaining = 3

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
        )
        assert enemy.damage == 0


class TestEvade:
    def test_evade_success_exhausts_enemy(self, game):
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]
        enemy_data = make_enemy_data(evade=2)
        game.register_card_data(enemy_data)

        enemy = CardInstance(
            instance_id="enemy_1", card_id="test_enemy",
            owner_id="scenario", controller_id="scenario",
        )
        game.state.cards_in_play["enemy_1"] = enemy
        inv = game.state.get_investigator("inv1")
        inv.threat_area.append("enemy_1")
        inv.actions_remaining = 3

        game.action_resolver.perform_action(
            "inv1", Action.EVADE, enemy_instance_id="enemy_1",
        )
        assert enemy.exhausted
        assert "enemy_1" not in inv.threat_area


class TestPlay:
    def test_play_asset_enters_play(self, game):
        asset_data = make_asset_data(id="knife", cost=1, slots=[SlotType.HAND])
        game.register_card_data(asset_data)

        inv = game.state.get_investigator("inv1")
        inv.hand.append("knife")
        inv.actions_remaining = 3
        inv.resources = 5

        game.action_resolver.perform_action("inv1", Action.PLAY, card_id="knife")
        assert "knife" not in inv.hand
        assert len(inv.play_area) == 1
        assert inv.resources == 4

    def test_play_event_goes_to_discard(self, game):
        event_data = make_event_data(id="lucky", cost=1)
        game.register_card_data(event_data)

        inv = game.state.get_investigator("inv1")
        inv.hand.append("lucky")
        inv.actions_remaining = 3
        inv.resources = 5

        game.action_resolver.perform_action("inv1", Action.PLAY, card_id="lucky")
        assert "lucky" not in inv.hand
        assert "lucky" in inv.discard

    def test_cannot_play_without_resources(self, game):
        asset_data = make_asset_data(id="expensive", cost=10)
        game.register_card_data(asset_data)

        inv = game.state.get_investigator("inv1")
        inv.hand.append("expensive")
        inv.actions_remaining = 3
        inv.resources = 2

        result = game.action_resolver.perform_action("inv1", Action.PLAY, card_id="expensive")
        assert not result


class TestAttackOfOpportunity:
    def test_draw_provokes_aoo(self, game):
        enemy_data = make_enemy_data(damage=1, horror=1)
        game.register_card_data(enemy_data)

        enemy = CardInstance(
            instance_id="enemy_1", card_id="test_enemy",
            owner_id="scenario", controller_id="scenario",
        )
        game.state.cards_in_play["enemy_1"] = enemy
        inv = game.state.get_investigator("inv1")
        inv.threat_area.append("enemy_1")
        inv.actions_remaining = 3
        initial_damage = inv.damage

        game.action_resolver.perform_action("inv1", Action.DRAW)
        assert inv.damage > initial_damage

    def test_fight_does_not_provoke_aoo(self, game):
        enemy_data = make_enemy_data(damage=1, horror=1, fight=3, health=5)
        game.register_card_data(enemy_data)
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]

        enemy = CardInstance(
            instance_id="enemy_1", card_id="test_enemy",
            owner_id="scenario", controller_id="scenario",
        )
        game.state.cards_in_play["enemy_1"] = enemy
        inv = game.state.get_investigator("inv1")
        inv.threat_area.append("enemy_1")
        inv.actions_remaining = 3
        initial_damage = inv.damage

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
        )
        # AoO should NOT fire; only fight damage to enemy
        assert inv.damage == initial_damage


class TestActionCost:
    def test_action_costs_one_action(self, game):
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        game.action_resolver.perform_action("inv1", Action.RESOURCE)
        assert inv.actions_remaining == 2

    def test_no_action_when_zero_remaining(self, game):
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 0
        result = game.action_resolver.perform_action("inv1", Action.RESOURCE)
        assert not result
