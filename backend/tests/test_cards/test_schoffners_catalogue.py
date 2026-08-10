"""Tests for Schoffner's Catalogue (Level 0)."""

import pytest
from backend.cards.survivor.schoffners_catalogue_lv0 import SchoffnersCatalogue
from backend.models.enums import PlayerClass
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="schoffners_catalogue_lv0", name="Schoffner's Catalogue", cost=2,
        card_class=PlayerClass.SURVIVOR, traits=["item", "tome"],
        uses={"secretss": 5},
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(SchoffnersCatalogue)
    return g


def _equip_catalogue(game):
    inv = game.state.get_investigator("inv1")
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id="schoffners_catalogue_lv0",
        owner_id="inv1", controller_id="inv1", uses={"secretss": 5},
    )
    inv.play_area.append(iid)
    game.card_registry.activate_card(
        "schoffners_catalogue_lv0", iid, game.event_bus)
    return iid


class TestSchoffnersCatalogue:
    def test_card_registered(self, game):
        assert "schoffners_catalogue_lv0" in game.card_registry.registered_cards

    def test_spend_secrets_as_resources(self, game):
        """花秘密当代付资源（1:1）。"""
        cat_id = _equip_catalogue(game)
        inv = game.state.get_investigator("inv1")
        inv.resources = 0
        impl = game.card_registry.active_instances[cat_id]

        assert impl.spend_for_item(game.state, "inv1", 2) is True
        assert inv.resources == 2
        assert game.state.get_card_instance(cat_id).uses["secretss"] == 3

    def test_discarded_when_out_of_secrets(self, game):
        """秘密耗尽即弃置。"""
        cat_id = _equip_catalogue(game)
        inv = game.state.get_investigator("inv1")
        impl = game.card_registry.active_instances[cat_id]

        assert impl.spend_for_item(game.state, "inv1", 5) is True
        assert cat_id not in inv.play_area
        assert "schoffners_catalogue_lv0" in inv.discard

    def test_cannot_overspend(self, game):
        cat_id = _equip_catalogue(game)
        impl = game.card_registry.active_instances[cat_id]
        assert impl.spend_for_item(game.state, "inv1", 6) is False
