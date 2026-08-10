"""Tests for In the Thick of It (Level 0)."""

import pytest
from backend.cards.neutral.in_the_thick_of_it_lv0 import InTheThickOfIt
from backend.engine.game import Game
from backend.tests.conftest import make_investigator_card, make_location_data


@pytest.fixture
def game():
    g = Game("test")
    inv_card = make_investigator_card(id="test_investigator")
    g.register_card_data(make_location_data())
    g.add_investigator("inv1", inv_card, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(InTheThickOfIt)
    return g


class TestInTheThickOfIt:
    def test_purchase_suffers_trauma_and_earns_xp(self, game):
        """购买：承受2点创伤（默认1+1），获得3点经验。"""
        impl = InTheThickOfIt()
        assert impl.purchase(game.state, "inv1") is True
        card = game.state.get_investigator("inv1").investigator_card
        assert card.physical_trauma == 1
        assert card.mental_trauma == 1
        assert card.experience == 3

    def test_purchase_custom_split(self, game):
        impl = InTheThickOfIt()
        assert impl.purchase(game.state, "inv1", physical=2, mental=0) is True
        card = game.state.get_investigator("inv1").investigator_card
        assert card.physical_trauma == 2
        assert card.mental_trauma == 0

    def test_purchase_rejects_invalid_split(self, game):
        impl = InTheThickOfIt()
        assert impl.purchase(game.state, "inv1", physical=1, mental=0) is False
