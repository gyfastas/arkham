"""Tests for Madame Labranche (Level 0)."""

import pytest
from backend.cards.survivor.madame_labranche_lv0 import MadameLabranche
from backend.models.enums import PlayerClass, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="madame_labranche_lv0", name="Madame Labranche", cost=2,
        card_class=PlayerClass.SURVIVOR, slots=[SlotType.ALLY],
        health=2, sanity=2, traits=["ally", "patron"],
    ))
    g.register_card_data(make_asset_data(id="deck_card", cost=1))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(MadameLabranche)
    return g


def _put_in_play(game):
    inv = game.state.get_investigator("inv1")
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id="madame_labranche_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    inv.play_area.append(iid)
    impl = game.card_registry.activate_card(
        "madame_labranche_lv0", iid, game.event_bus, chaos_bag=game.chaos_bag)
    return iid, impl


class TestMadameLabranche:
    def test_card_registered(self, game):
        assert "madame_labranche_lv0" in game.card_registry.registered_cards

    def test_draw_when_hand_empty(self, game):
        """手牌为空：横置抽1张牌。"""
        iid, impl = _put_in_play(game)
        inv = game.state.get_investigator("inv1")
        inv.hand = []
        inv.deck = ["deck_card"]

        assert impl.activate_draw(game.state, "inv1") is True
        assert inv.hand == ["deck_card"]
        assert game.state.get_card_instance(iid).exhausted is True

    def test_draw_rejected_with_cards_in_hand(self, game):
        """手牌非空时不能启动抽牌。"""
        iid, impl = _put_in_play(game)
        inv = game.state.get_investigator("inv1")
        inv.hand = ["deck_card"]
        inv.deck = ["deck_card"]

        assert impl.activate_draw(game.state, "inv1") is False
        assert game.state.get_card_instance(iid).exhausted is False

    def test_gain_resource_when_broke(self, game):
        """资源为0：横置获得1资源。"""
        iid, impl = _put_in_play(game)
        inv = game.state.get_investigator("inv1")
        inv.resources = 0

        assert impl.activate_gain_resource(game.state, "inv1") is True
        assert inv.resources == 1
        assert game.state.get_card_instance(iid).exhausted is True

    def test_gain_resource_rejected_with_resources(self, game):
        iid, impl = _put_in_play(game)
        inv = game.state.get_investigator("inv1")
        inv.resources = 2

        assert impl.activate_gain_resource(game.state, "inv1") is False
        assert inv.resources == 2
        assert game.state.get_card_instance(iid).exhausted is False

    def test_exhausted_blocks_both_abilities(self, game):
        iid, impl = _put_in_play(game)
        inv = game.state.get_investigator("inv1")
        game.state.get_card_instance(iid).exhausted = True
        inv.hand = []
        inv.resources = 0
        inv.deck = ["deck_card"]

        assert impl.activate_draw(game.state, "inv1") is False
        assert impl.activate_gain_resource(game.state, "inv1") is False
