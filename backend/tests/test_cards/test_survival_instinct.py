"""Tests for Survival Instinct (Level 0)."""

import pytest
from backend.cards.survivor.survival_instinct_lv0 import SurvivalInstinct
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data, make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(agility=3)
    g.register_card_data(inv_data)
    loc_a = make_location_data(id="loc_a", connections=["loc_b"])
    loc_b = make_location_data(id="loc_b", connections=["loc_a"])
    g.register_card_data(loc_a)
    g.register_card_data(loc_b)
    g.register_card_data(make_skill_data(
        id="survival_instinct_lv0", skill_icons={"agility": 1}))
    g.register_card_data(make_enemy_data(fight=3, health=3, evade=3))
    g.add_investigator("inv1", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_a, clues=0)
    g.add_location("loc_b", loc_b, clues=0)
    g.card_registry.register_class(SurvivalInstinct)
    return g


def _spawn_enemy(game, instance_id):
    game.state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.get_investigator("inv1").threat_area.append(instance_id)


def _evade(game, token):
    inv = game.state.get_investigator("inv1")
    inv.hand = ["survival_instinct_lv0"]
    inv.actions_remaining = 3
    game.chaos_bag.tokens = [token]
    game.action_resolver.perform_action(
        "inv1", Action.EVADE,
        enemy_instance_id="enemy_1",
        committed_cards=["survival_instinct_lv0"],
    )
    return inv


class TestSurvivalInstinct:
    def test_card_registered(self, game):
        assert "survival_instinct_lv0" in game.card_registry.registered_cards

    def test_successful_evade_disengages_others_and_moves(self, game):
        """躲避成功后：与其他交战敌人脱离，并移动到连接地点。"""
        _spawn_enemy(game, "enemy_1")
        _spawn_enemy(game, "enemy_2")
        inv = _evade(game, ChaosTokenType.ZERO)

        loc_a = game.state.get_location("loc_a")
        enemy_1 = game.state.get_card_instance("enemy_1")
        # 被躲避的敌人横置留在原地点
        assert enemy_1.exhausted is True
        assert "enemy_1" in loc_a.enemies
        # 其他交战敌人脱离（不横置），留在原地点
        assert "enemy_2" not in inv.threat_area
        assert "enemy_2" in loc_a.enemies
        assert game.state.get_card_instance("enemy_2").exhausted is False
        # 移动到连接地点
        assert inv.location_id == "loc_b"
        assert not inv.threat_area

    def test_failed_evade_no_effect(self, game):
        """躲避失败：不脱离、不移动。"""
        _spawn_enemy(game, "enemy_1")
        _spawn_enemy(game, "enemy_2")
        inv = _evade(game, ChaosTokenType.AUTO_FAIL)

        assert inv.location_id == "loc_a"
        assert "enemy_2" in inv.threat_area
