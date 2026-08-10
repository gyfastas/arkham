"""Tests for Bait and Switch (Level 3)."""

import pytest

from backend.cards.survivor.bait_and_switch_lv3 import BaitAndSwitchLv3
from backend.engine.game import Game
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc_a = make_location_data(id="loc_a", connections=["loc_b"])
    loc_b = make_location_data(id="loc_b", connections=["loc_a"])
    g.register_card_data(loc_a)
    g.register_card_data(loc_b)
    g.register_card_data(make_event_data(
        id="bait_and_switch_lv3", name="Bait and Switch", cost=1))
    g.register_card_data(make_enemy_data(fight=3, health=3, evade=2))
    g.add_investigator("inv1", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_a, clues=0)
    g.add_location("loc_b", loc_b, clues=0)
    g.card_registry.register_class(BaitAndSwitchLv3)
    return g


def _enemy(game, instance_id):
    game.state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )


class TestBaitAndSwitchLv3:
    def test_card_registered(self, game):
        assert "bait_and_switch_lv3" in game.card_registry.registered_cards

    def test_mode1_evade_and_move_enemy(self, game):
        """模式1：躲避交战敌人并移动到连接地点。"""
        inv = game.state.get_investigator("inv1")
        _enemy(game, "enemy_1")
        inv.threat_area.append("enemy_1")

        assert BaitAndSwitchLv3.resolve(
            game.state, "inv1", "enemy_1") is True
        enemy = game.state.get_card_instance("enemy_1")
        assert enemy.exhausted is True
        assert "enemy_1" not in inv.threat_area
        assert "enemy_1" in game.state.get_location("loc_b").enemies

    def test_mode2_switch_locations(self, game):
        """模式2：躲避连接地点的敌人并与其交换地点。"""
        inv = game.state.get_investigator("inv1")
        _enemy(game, "enemy_1")
        game.state.get_location("loc_b").enemies.append("enemy_1")

        assert BaitAndSwitchLv3.resolve(
            game.state, "inv1", "enemy_1", switch=True) is True
        enemy = game.state.get_card_instance("enemy_1")
        assert enemy.exhausted is True
        assert inv.location_id == "loc_b"
        assert "enemy_1" in game.state.get_location("loc_a").enemies
        assert "enemy_1" not in game.state.get_location("loc_b").enemies

    def test_mode2_rejects_enemy_at_own_location(self, game):
        """模式2仅对连接地点的敌人可用。"""
        inv = game.state.get_investigator("inv1")
        _enemy(game, "enemy_1")
        inv.threat_area.append("enemy_1")
        assert BaitAndSwitchLv3.resolve(
            game.state, "inv1", "enemy_1", switch=True) is False
