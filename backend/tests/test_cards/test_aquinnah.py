"""Tests for Aquinnah (Level 1 and Level 3)."""

import pytest
from backend.cards.survivor.aquinnah_lv1 import AquinnahLv1
from backend.cards.survivor.aquinnah_lv3 import AquinnahLv3
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

    aq1_data = make_asset_data(
        id="aquinnah_lv1", name="Aquinnah", cost=5,
        card_class=PlayerClass.SURVIVOR,
        slots=[SlotType.ALLY], health=1, sanity=4,
        traits=["ally"],
    )
    g.register_card_data(aq1_data)

    aq3_data = make_asset_data(
        id="aquinnah_lv3", name="Aquinnah", cost=4,
        card_class=PlayerClass.SURVIVOR,
        slots=[SlotType.ALLY], health=1, sanity=4,
        traits=["ally"],
    )
    g.register_card_data(aq3_data)

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(AquinnahLv1)
    g.card_registry.register_class(AquinnahLv3)
    return g


class TestAquinnah:
    def test_lv1_registered(self, game):
        assert "aquinnah_lv1" in game.card_registry.registered_cards

    def test_lv3_registered(self, game):
        assert "aquinnah_lv3" in game.card_registry.registered_cards

    def test_lv1_has_sanity_soak(self, game):
        data = game.state.card_database["aquinnah_lv1"]
        assert data.sanity == 4
