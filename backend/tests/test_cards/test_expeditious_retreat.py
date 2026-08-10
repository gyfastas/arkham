"""Tests for Expeditious Retreat (Level 1)."""

import pytest

from backend.cards.survivor.expeditious_retreat_lv1 import ExpeditiousRetreat
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
    make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(agility=5)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_skill_data(
        id="expeditious_retreat_lv1", skill_icons={"agility": 1}))
    g.register_card_data(make_enemy_data(fight=3, health=3, evade=2))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(ExpeditiousRetreat)
    return g


def _engage(game, instance_id):
    inv = game.state.get_investigator("inv1")
    game.state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    inv.threat_area.append(instance_id)


class TestExpeditiousRetreat:
    def test_card_registered(self, game):
        assert "expeditious_retreat_lv1" in \
            game.card_registry.registered_cards

    def test_success_by_2_auto_evades_another_enemy(self, game):
        """躲避成功且超出≥2：自动躲避另一名交战敌人。"""
        _engage(game, "enemy_1")
        _engage(game, "enemy_2")
        inv = game.state.get_investigator("inv1")
        inv.hand = ["expeditious_retreat_lv1"]
        loc = game.state.get_location("test_location")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]  # 5+1+2=8 vs 2，超出6

        assert game.action_resolver.perform_action(
            "inv1", Action.EVADE, enemy_instance_id="enemy_1",
            committed_cards=["expeditious_retreat_lv1"]) is True
        enemy_1 = game.state.get_card_instance("enemy_1")
        enemy_2 = game.state.get_card_instance("enemy_2")
        # 首个敌人被引擎躲避，另一名被卡面自动躲避
        assert enemy_1.exhausted is True
        assert enemy_2.exhausted is True
        assert inv.threat_area == []
        assert "enemy_1" in loc.enemies
        assert "enemy_2" in loc.enemies

    def test_success_by_1_no_extra_evade(self, game):
        """超出不足2：不自动躲避另一名敌人。"""
        _engage(game, "enemy_1")
        _engage(game, "enemy_2")
        inv = game.state.get_investigator("inv1")
        inv.hand = ["expeditious_retreat_lv1"]
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_5]  # 8-5=3 vs 2，超出1

        game.action_resolver.perform_action(
            "inv1", Action.EVADE, enemy_instance_id="enemy_1",
            committed_cards=["expeditious_retreat_lv1"])
        enemy_2 = game.state.get_card_instance("enemy_2")
        assert enemy_2.exhausted is False
        assert "enemy_2" in inv.threat_area
