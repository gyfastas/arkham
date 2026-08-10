"""Tests for Dumb Luck (Level 0)."""

import pytest

from backend.cards.survivor.dumb_luck_lv0 import DumbLuck
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
    inv_data = make_investigator_data(agility=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="dumb_luck_lv0", name="Dumb Luck", cost=2, fast=True))
    g.register_card_data(make_enemy_data(fight=3, health=3, evade=3))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(DumbLuck)
    impl = DumbLuck("impl_dumb_luck")
    impl.register(g.event_bus, "impl_dumb_luck")
    inv = g.state.get_investigator("inv1")
    g.state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    inv.threat_area.append("enemy_1")
    return g


class TestDumbLuck:
    def test_card_registered(self, game):
        assert "dumb_luck_lv0" in game.card_registry.registered_cards

    def test_fail_evade_by_2_topdecks_enemy(self, game):
        """躲避失败且差值≤2：自动打出，敌人放到遭遇牌堆顶。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["dumb_luck_lv0"]
        inv.resources = 5
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_2]  # 1 vs 3，差2

        assert game.action_resolver.perform_action(
            "inv1", Action.EVADE, enemy_instance_id="enemy_1") is True
        assert game.state.scenario.encounter_deck[0] == "test_enemy"
        assert "enemy_1" not in inv.threat_area
        assert "enemy_1" not in game.state.cards_in_play
        assert "dumb_luck_lv0" in inv.discard
        assert inv.resources == 3

    def test_fail_by_3_no_trigger(self, game):
        """失败差值>2：不触发。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["dumb_luck_lv0"]
        inv.resources = 5
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_3]  # 0 vs 3，差3

        game.action_resolver.perform_action(
            "inv1", Action.EVADE, enemy_instance_id="enemy_1")
        assert "enemy_1" in inv.threat_area
        assert "dumb_luck_lv0" in inv.hand
        assert game.state.scenario.encounter_deck == []
