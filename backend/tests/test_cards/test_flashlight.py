"""Tests for Flashlight (Level 0)."""

import pytest
from backend.cards.neutral.flashlight_lv0 import Flashlight
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

    fl_data = make_asset_data(
        id="flashlight_lv0", name="Flashlight", cost=2,
        slots=[SlotType.HAND], traits=["item", "tool"],
        uses={"supply": 3},
    )
    g.register_card_data(fl_data)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=2)
    g.card_registry.register_class(Flashlight)
    return g


class TestFlashlight:
    def test_card_registered(self, game):
        assert "flashlight_lv0" in game.card_registry.registered_cards

    def test_has_uses(self, game):
        data = game.state.card_database["flashlight_lv0"]
        assert data.uses == {"supply": 3}
