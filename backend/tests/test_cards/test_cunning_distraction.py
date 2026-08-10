"""Tests for Cunning Distraction (Level 0)."""

import pytest
from backend.cards.survivor.cunning_distraction_lv0 import CunningDistraction
from backend.models.enums import Action, PlayerClass
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data, make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data(connections=[])
    g.register_card_data(loc)
    g.register_card_data(make_event_data(id="cunning_distraction_lv0", cost=5, fast=True))
    g.register_card_data(make_enemy_data())
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(CunningDistraction)
    return g


def _spawn_enemy(game, instance_id, engaged):
    game.state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    if engaged:
        game.state.get_investigator("inv1").threat_area.append(instance_id)
    else:
        game.state.get_location("test_location").enemies.append(instance_id)


class TestCunningDistraction:
    def test_card_registered(self, game):
        assert "cunning_distraction_lv0" in game.card_registry.registered_cards

    def test_evades_all_enemies_at_location_without_moving(self, game):
        """自动躲避所在地点的所有敌人（交战+未交战），调查员不移动。"""
        _spawn_enemy(game, "enemy_1", engaged=True)
        _spawn_enemy(game, "enemy_2", engaged=False)
        inv = game.state.get_investigator("inv1")
        inv.hand = ["cunning_distraction_lv0"]
        inv.resources = 5

        ok = game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="cunning_distraction_lv0")
        assert ok

        loc = game.state.get_location("test_location")
        assert not inv.threat_area
        assert "enemy_1" in loc.enemies and "enemy_2" in loc.enemies
        assert game.state.get_card_instance("enemy_1").exhausted is True
        assert game.state.get_card_instance("enemy_2").exhausted is True
        assert inv.location_id == "test_location"  # 不移动
        assert inv.resources == 0
