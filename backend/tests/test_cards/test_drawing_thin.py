"""Tests for Drawing Thin (Level 0)."""

import pytest

from backend.cards.survivor.drawing_thin_lv0 import DrawingThin
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)
    loc = make_location_data(shroud=2)
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="drawing_thin_lv0", name="Drawing Thin", cost=0,
        traits=["talent"]))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=3)
    g.card_registry.register_class(DrawingThin)
    return g


def _play_drawing_thin(game):
    inv = game.state.get_investigator("inv1")
    inv.resources = 3
    inv.hand = ["drawing_thin_lv0"]
    assert game.action_resolver.perform_action(
        "inv1", Action.PLAY, card_id="drawing_thin_lv0") is True
    iid = next(i for i in inv.play_area
               if game.state.get_card_instance(i).card_id == "drawing_thin_lv0")
    return inv, iid


class TestDrawingThin:
    def test_card_registered(self, game):
        assert "drawing_thin_lv0" in game.card_registry.registered_cards

    def test_initiate_test_raises_difficulty_and_gains_resources(self, game):
        """发动检定时消耗：难度+2，获得2资源。"""
        inv, iid = _play_drawing_thin(game)
        resources_before = inv.resources
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        assert game.action_resolver.perform_action(
            "inv1", Action.INVESTIGATE) is True
        inst = game.state.get_card_instance(iid)
        assert inst.exhausted is True
        assert inv.resources == resources_before + 2
        # 难度2+2=4 > 智力3：调查失败，未发现线索
        assert inv.clues == 0
        assert game.state.get_location("test_location").clues == 3

    def test_exhausted_no_trigger(self, game):
        """已横置时不触发：难度不变、不加资源。"""
        inv, iid = _play_drawing_thin(game)
        inst = game.state.get_card_instance(iid)
        inst.exhausted = True
        resources_before = inv.resources
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        game.action_resolver.perform_action("inv1", Action.INVESTIGATE)
        assert inv.resources == resources_before
        assert inv.clues == 1  # 3 vs 难度2：成功
