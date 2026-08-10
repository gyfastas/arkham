"""Tests for Manipulate Destiny (Level 2)."""

import pytest
from backend.cards.neutral.manipulate_destiny_lv2 import ManipulateDestiny
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


def _build_game(tokens):
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data())
    g.register_card_data(make_location_data())
    g.register_card_data(make_event_data(
        id="manipulate_destiny_lv2", name="Manipulate Destiny", cost=1,
    ))
    g.register_card_data(make_enemy_data(
        id="ghoul", name="Ghoul", fight=2, health=5, evade=2,
    ))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(ManipulateDestiny)
    inv = g.state.get_investigator("inv1")
    inv.hand.append("manipulate_destiny_lv2")
    inv.resources = 5
    g.chaos_bag.tokens = list(tokens)
    return g


def _spawn(game):
    enemy = CardInstance(
        instance_id="enemy_1", card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play["enemy_1"] = enemy
    game.state.get_investigator("inv1").threat_area.append("enemy_1")
    return enemy


def _play(game):
    game.action_resolver.perform_action(
        "inv1", Action.PLAY, card_id="manipulate_destiny_lv2",
    )


class TestManipulateDestiny:
    def test_curse_deals_2_damage(self):
        """揭示[curse]：对同地点敌人造成2点伤害；揭示的标记结算后放回。"""
        game = _build_game([ChaosTokenType.CURSE, ChaosTokenType.ZERO])
        enemy = _spawn(game)
        _play(game)
        assert enemy.damage == 2
        # 所有揭示的标记已放回袋中
        assert sorted(t.value for t in game.chaos_bag.tokens) == ["0", "curse"]

    def test_bless_heals_2_damage(self):
        """揭示[bless]：治愈你2点伤害。"""
        game = _build_game([ChaosTokenType.BLESS])
        inv = game.state.get_investigator("inv1")
        inv.damage = 3
        _play(game)
        assert inv.damage == 1
