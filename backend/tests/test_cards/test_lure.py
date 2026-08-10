"""Tests for Lure (Level 2)."""

import pytest
from backend.cards.survivor.lure_lv2 import Lure
from backend.models.enums import Action, GameEvent, PlayerClass
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)
from backend.engine.event_bus import EventContext
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data(connections=["loc_b"])
    g.register_card_data(loc)
    loc_b = make_location_data(id="loc_b", name="Location B",
                               connections=["test_location"])
    g.register_card_data(loc_b)
    g.register_card_data(make_event_data(
        id="lure_lv2", name="Lure", cost=1,
        card_class=PlayerClass.SURVIVOR))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.add_location("loc_b", loc_b, clues=0)
    g.card_registry.register_class(Lure)
    return g


class TestLure:
    def test_card_registered(self, game):
        assert "lure_lv2" in game.card_registry.registered_cards

    def test_attach_and_forced_discard_at_round_end(self, game):
        """打出叠加到所在地点；回合结束时强制丢弃。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["lure_lv2"]
        inv.resources = 3

        assert game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="lure_lv2") is True
        assert game.state.scenario.vars["lure_locations"] == ["test_location"]

        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.ROUND_ENDS))
        assert game.state.scenario.vars["lure_locations"] == []
