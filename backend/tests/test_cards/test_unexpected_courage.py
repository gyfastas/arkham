"""Tests for Unexpected Courage (Level 0)."""

import pytest
from backend.cards.neutral.unexpected_courage_lv0 import UnexpectedCourage
from backend.engine.game import Game
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(UnexpectedCourage)
    return g


class TestUnexpectedCourage:
    def test_card_registered(self, game):
        assert "unexpected_courage_lv0" in game.card_registry.registered_cards
