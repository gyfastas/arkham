"""Tests for Belly of the Beast (Level 0)."""

import pytest

from backend.cards.survivor.belly_of_the_beast_lv0 import BellyOfTheBeast
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(agility=5)
    g.register_card_data(inv_data)
    loc = make_location_data(clue_value=3)
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="belly_of_the_beast_lv0", name="Belly of the Beast",
        cost=1, fast=True))
    g.register_card_data(make_enemy_data(fight=3, health=3, evade=3))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=2)
    g.card_registry.register_class(BellyOfTheBeast)
    impl = BellyOfTheBeast("impl_botb")
    impl.register(g.event_bus, "impl_botb")
    return g


def _engage_enemy(game):
    inv = game.state.get_investigator("inv1")
    game.state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    inv.threat_area.append("enemy_1")
    return inv


class TestBellyOfTheBeast:
    def test_card_registered(self, game):
        assert "belly_of_the_beast_lv0" in game.card_registry.registered_cards

    def test_evade_by_2_discovers_clue(self, game):
        """成功躲避且超出2点：自动打出，发现敌人所在地点1个线索。"""
        inv = _engage_enemy(game)
        inv.hand = ["belly_of_the_beast_lv0"]
        inv.resources = 3
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]  # 5 vs 3，超出2

        assert game.action_resolver.perform_action(
            "inv1", Action.EVADE, enemy_instance_id="enemy_1") is True
        assert inv.clues == 1
        assert game.state.get_location("test_location").clues == 1
        assert "belly_of_the_beast_lv0" in inv.discard
        assert inv.resources == 2

    def test_evade_by_1_no_trigger(self, game):
        """仅超出1点：不触发。"""
        inv = _engage_enemy(game)
        inv.hand = ["belly_of_the_beast_lv0"]
        inv.resources = 3
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_1]  # 4 vs 3，超出1

        assert game.action_resolver.perform_action(
            "inv1", Action.EVADE, enemy_instance_id="enemy_1") is True
        assert inv.clues == 0
        assert "belly_of_the_beast_lv0" in inv.hand
