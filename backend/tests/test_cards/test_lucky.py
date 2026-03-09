"""Tests for Lucky! (Level 0 and Level 2)."""

import pytest
from backend.cards.survivor.lucky_lv0 import Lucky
from backend.cards.survivor.lucky_lv2 import LuckyLv2
from backend.models.enums import PlayerClass
from backend.tests.conftest import make_investigator_data, make_location_data
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(Lucky)
    g.card_registry.register_class(LuckyLv2)
    return g


class TestLucky:
    def test_lv0_registered(self, game):
        assert "lucky_lv0" in game.card_registry.registered_cards

    def test_lv2_registered(self, game):
        assert "lucky_lv2" in game.card_registry.registered_cards
