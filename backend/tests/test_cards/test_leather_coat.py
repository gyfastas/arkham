"""Tests for Leather Coat (Level 0)."""

import pytest
from backend.cards.survivor.leather_coat_lv0 import LeatherCoat
from backend.models.enums import CardType, PlayerClass, SlotType
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import make_investigator_data, make_asset_data, make_location_data
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)

    coat_data = make_asset_data(
        id="leather_coat_lv0", name="Leather Coat", cost=0,
        card_class=PlayerClass.SURVIVOR, slots=[SlotType.BODY],
        health=2, traits=["item", "armor"],
    )
    g.register_card_data(coat_data)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(LeatherCoat)
    return g


class TestLeatherCoat:
    def test_card_registered(self, game):
        assert "leather_coat_lv0" in game.card_registry.registered_cards

    def test_has_health_soak(self, game):
        coat_data = game.state.card_database["leather_coat_lv0"]
        assert coat_data.health == 2
