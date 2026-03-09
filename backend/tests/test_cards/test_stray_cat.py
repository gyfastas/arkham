"""Tests for Stray Cat (Level 0)."""

import pytest
from backend.cards.survivor.stray_cat_lv0 import StrayCat
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

    cat_data = make_asset_data(
        id="stray_cat_lv0", name="Stray Cat", cost=1,
        card_class=PlayerClass.SURVIVOR,
        slots=[SlotType.ALLY], health=1,
        traits=["ally", "creature"],
    )
    g.register_card_data(cat_data)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(StrayCat)
    return g


class TestStrayCat:
    def test_card_registered(self, game):
        assert "stray_cat_lv0" in game.card_registry.registered_cards

    def test_has_health(self, game):
        cat_data = game.state.card_database["stray_cat_lv0"]
        assert cat_data.health == 1
