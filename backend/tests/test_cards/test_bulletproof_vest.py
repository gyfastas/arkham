"""Tests for Bulletproof Vest (Level 3)."""

import pytest
from backend.cards.neutral.bulletproof_vest_lv3 import BulletproofVest
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

    vest_data = make_asset_data(
        id="bulletproof_vest_lv3", name="Bulletproof Vest", cost=2,
        slots=[SlotType.BODY], health=4, traits=["item", "armor"],
    )
    g.register_card_data(vest_data)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(BulletproofVest)
    return g


class TestBulletproofVest:
    def test_card_registered(self, game):
        assert "bulletproof_vest_lv3" in game.card_registry.registered_cards

    def test_has_4_health_soak(self, game):
        data = game.state.card_database["bulletproof_vest_lv3"]
        assert data.health == 4
