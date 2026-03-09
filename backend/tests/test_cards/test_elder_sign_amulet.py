"""Tests for Elder Sign Amulet (Level 3)."""

import pytest
from backend.cards.neutral.elder_sign_amulet_lv3 import ElderSignAmulet
from backend.models.enums import SlotType
from backend.tests.conftest import make_investigator_data, make_asset_data, make_location_data
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)

    amulet_data = make_asset_data(
        id="elder_sign_amulet_lv3", name="Elder Sign Amulet", cost=2,
        slots=[SlotType.ACCESSORY], sanity=4, traits=["item", "relic"],
    )
    g.register_card_data(amulet_data)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(ElderSignAmulet)
    return g


class TestElderSignAmulet:
    def test_card_registered(self, game):
        assert "elder_sign_amulet_lv3" in game.card_registry.registered_cards

    def test_has_4_sanity_soak(self, game):
        data = game.state.card_database["elder_sign_amulet_lv3"]
        assert data.sanity == 4
