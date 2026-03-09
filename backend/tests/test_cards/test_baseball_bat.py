"""Tests for Baseball Bat (Level 0)."""

import pytest
from backend.cards.survivor.baseball_bat_lv0 import BaseballBat
from backend.models.enums import PlayerClass, SlotType
from backend.tests.conftest import make_investigator_data, make_asset_data, make_location_data
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)

    bat_data = make_asset_data(
        id="baseball_bat_lv0", name="Baseball Bat", cost=2,
        card_class=PlayerClass.SURVIVOR,
        slots=[SlotType.HAND, SlotType.HAND],
        traits=["item", "weapon", "melee"],
    )
    g.register_card_data(bat_data)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(BaseballBat)
    return g


class TestBaseballBat:
    def test_card_registered(self, game):
        assert "baseball_bat_lv0" in game.card_registry.registered_cards

    def test_takes_two_hand_slots(self, game):
        bat_data = game.state.card_database["baseball_bat_lv0"]
        assert bat_data.slots == [SlotType.HAND, SlotType.HAND]
