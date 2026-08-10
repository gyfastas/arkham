"""Tests for Obscure Studies (Level 0)."""

import pytest
from backend.cards.neutral.obscure_studies_lv0 import (
    ObscureStudies, beneath_key,
)
from backend.engine.game import Game
from backend.models.enums import Action
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data())
    g.register_card_data(make_location_data())
    g.register_card_data(make_event_data(
        id="obscure_studies_lv0", name="Obscure Studies", fast=True,
    ))
    g.register_card_data(make_event_data(id="guts_lv0", name="Guts"))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(ObscureStudies)
    inv = g.state.get_investigator("inv1")
    inv.hand.append("obscure_studies_lv0")
    inv.resources = 5
    return g


class TestObscureStudies:
    def test_returns_beneath_card_and_takes_its_place(self, game):
        """打出：阿曼达下的牌返回手牌，隐秘研习放到她之下。"""
        game.state.scenario.vars[beneath_key("inv1")] = ["guts_lv0"]
        inv = game.state.get_investigator("inv1")
        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="obscure_studies_lv0",
        )
        assert "guts_lv0" in inv.hand
        assert game.state.scenario.vars[beneath_key("inv1")] == \
            ["obscure_studies_lv0"]

    def test_no_beneath_card(self, game):
        """阿曼达下无牌：仅将本卡放到她之下。"""
        inv = game.state.get_investigator("inv1")
        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="obscure_studies_lv0",
        )
        assert game.state.scenario.vars[beneath_key("inv1")] == \
            ["obscure_studies_lv0"]
