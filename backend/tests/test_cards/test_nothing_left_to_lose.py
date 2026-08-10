"""Tests for Nothing Left to Lose (Level 3)."""

import pytest
from backend.cards.survivor.nothing_left_to_lose_lv3 import NothingLeftToLose
from backend.models.enums import Action, PlayerClass
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
    make_skill_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="nothing_left_to_lose_lv3", name="Nothing Left to Lose", cost=0,
        card_class=PlayerClass.SURVIVOR))
    g.register_card_data(make_skill_data(id="filler", skill_icons={}))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(NothingLeftToLose)
    return g


class TestNothingLeftToLose:
    def test_card_registered(self, game):
        assert "nothing_left_to_lose_lv3" in game.card_registry.registered_cards

    def test_refill_and_remove_from_game(self, game):
        """补至5资源/5手牌，随后移出游戏（不进弃牌堆）。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["nothing_left_to_lose_lv3"]
        inv.deck = ["filler"] * 8
        inv.resources = 1

        assert game.action_resolver.perform_action(
            "inv1", Action.PLAY,
            card_id="nothing_left_to_lose_lv3") is True

        assert inv.resources == 5
        assert len(inv.hand) == 5
        assert "nothing_left_to_lose_lv3" not in inv.discard
        assert "nothing_left_to_lose_lv3" in \
            game.state.scenario.vars["removed_from_game"]

    def test_no_overgain(self, game):
        """已达5资源/5手牌时不增补。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["nothing_left_to_lose_lv3"] + ["filler"] * 6
        inv.resources = 7

        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="nothing_left_to_lose_lv3")

        assert inv.resources == 7
        assert len(inv.hand) == 6  # 事件离手，未补抽
