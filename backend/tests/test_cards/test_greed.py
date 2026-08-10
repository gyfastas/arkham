"""Tests for Greed (Level 0 weakness)."""

import pytest
from backend.cards.neutral.greed_lv0 import Greed
from backend.engine.draw_hooks import emit_card_drawn
from backend.engine.game import Game
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data())
    g.register_card_data(make_location_data())
    g.register_card_data(make_event_data(id="greed_lv0", name="Greed"))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(Greed)
    return g


def _draw_greed(game, resources):
    inv = game.state.get_investigator("inv1")
    inv.resources = resources
    inv.hand.append("greed_lv0")
    emit_card_drawn(game.state, game.event_bus, game.card_registry,
                    inv, "greed_lv0", chaos_bag=game.chaos_bag)
    return inv


class TestGreed:
    def test_full_horror_at_zero_resources(self, game):
        """0资源：1+1+1+1=4点恐惧。"""
        inv = _draw_greed(game, 0)
        assert inv.horror == 4

    def test_horror_scales_with_resources(self, game):
        """4资源：1+1(≤10)+1(≤5)=3点恐惧；11资源：仅1点。"""
        inv = _draw_greed(game, 4)
        assert inv.horror == 3

    def test_one_horror_above_10_resources(self, game):
        inv = _draw_greed(game, 11)
        assert inv.horror == 1

    def test_card_discarded_after_revelation(self, game):
        inv = _draw_greed(game, 20)
        assert "greed_lv0" not in inv.hand
        assert "greed_lv0" in inv.discard
