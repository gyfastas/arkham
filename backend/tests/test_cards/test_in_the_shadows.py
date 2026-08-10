"""Tests for In the Shadows (Level 0)."""

import pytest
from backend.cards.neutral.in_the_shadows_lv0 import InTheShadows
from backend.engine.game import Game
from backend.models.enums import Action
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data())
    g.register_card_data(make_location_data())
    g.register_card_data(make_event_data(
        id="in_the_shadows_lv0", name="In the Shadows", fast=True,
    ))
    g.register_card_data(make_enemy_data(
        id="ghoul", name="Ghoul", fight=2, health=5, evade=2,
    ))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(InTheShadows)
    inv = g.state.get_investigator("inv1")
    inv.hand.append("in_the_shadows_lv0")
    inv.resources = 5

    enemy = CardInstance(
        instance_id="enemy_1", card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    g.state.cards_in_play["enemy_1"] = enemy
    inv.threat_area.append("enemy_1")
    return g


def _play(game):
    game.action_resolver.perform_action(
        "inv1", Action.PLAY, card_id="in_the_shadows_lv0",
    )


class TestInTheShadows:
    def test_disengage_on_play(self, game):
        """打出：脱离所有交战敌人。"""
        _play(game)
        inv = game.state.get_investigator("inv1")
        assert inv.threat_area == []
        assert "enemy_1" in game.state.get_location("test_location").enemies

    def test_enemies_cannot_engage_you(self, game):
        """本轮敌人与你交战会被立即解除。"""
        _play(game)
        game.action_resolver.perform_action(
            "inv1", Action.ENGAGE, enemy_instance_id="enemy_1",
        )
        inv = game.state.get_investigator("inv1")
        assert "enemy_1" not in inv.threat_area
        assert "enemy_1" in game.state.get_location("test_location").enemies

    def test_you_cannot_deal_damage(self, game):
        """本轮你对敌人造成的伤害归零。"""
        _play(game)
        game.damage_engine.deal_damage_to_enemy(
            "enemy_1", 2, investigator_id="inv1",
        )
        enemy = game.state.get_card_instance("enemy_1")
        assert enemy.damage == 0
