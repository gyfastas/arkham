"""Tests for Scavenging (Level 0)."""

import pytest
from backend.cards.survivor.scavenging_lv0 import Scavenging
from backend.models.enums import PlayerClass
from backend.tests.conftest import make_investigator_data, make_asset_data, make_location_data
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)

    scav_data = make_asset_data(
        id="scavenging_lv0", name="Scavenging", cost=1,
        card_class=PlayerClass.SURVIVOR, traits=["talent"],
    )
    g.register_card_data(scav_data)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(Scavenging)
    return g


class TestScavenging:
    def test_card_registered(self, game):
        assert "scavenging_lv0" in game.card_registry.registered_cards
