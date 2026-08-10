"""Tests for Lodge "Debts" (Level 0 weakness)."""

import pytest
from backend.cards.neutral.lodge_debts_lv0 import LodgeDebts
from backend.engine.game import Game
from backend.models.enums import Action
from backend.tests.conftest import (
    make_event_data, make_investigator_card, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_card = make_investigator_card(id="test_investigator")
    g.register_card_data(make_location_data())
    g.register_card_data(make_event_data(
        id="lodge_debts_lv0", name='Lodge "Debts"', cost=10,
    ))
    g.add_investigator("inv1", inv_card, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(LodgeDebts)
    return g


class TestLodgeDebts:
    def test_play_removes_from_game(self, game):
        """打出：记录为移出游戏。"""
        inv = game.state.get_investigator("inv1")
        inv.hand.append("lodge_debts_lv0")
        inv.resources = 10
        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="lodge_debts_lv0",
        )
        assert "lodge_debts_lv0" in \
            game.state.scenario.vars["removed_from_game"]

    def test_mental_trauma_if_in_hand_at_game_end(self, game):
        """游戏结束时仍在手牌：承受1点精神创伤。"""
        inv = game.state.get_investigator("inv1")
        inv.hand.append("lodge_debts_lv0")
        impl = LodgeDebts()
        assert impl.on_game_end(game.state, "inv1") is True
        assert inv.investigator_card.mental_trauma == 1

    def test_no_trauma_if_not_in_hand(self, game):
        impl = LodgeDebts()
        assert impl.on_game_end(game.state, "inv1") is False
        inv = game.state.get_investigator("inv1")
        assert inv.investigator_card.mental_trauma == 0
