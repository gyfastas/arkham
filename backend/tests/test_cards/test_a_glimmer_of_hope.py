"""Tests for A Glimmer of Hope (Level 0)."""

import pytest

from backend.cards.survivor.a_glimmer_of_hope_lv0 import AGlimmerOfHope
from backend.engine.game import Game
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="a_glimmer_of_hope_lv0", name="A Glimmer of Hope", cost=1))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(AGlimmerOfHope)
    return g


class TestAGlimmerOfHope:
    def test_card_registered(self, game):
        assert "a_glimmer_of_hope_lv0" in game.card_registry.registered_cards

    def test_play_from_discard_returns_all_copies(self, game):
        """从弃牌堆打出：所有希望微光（含本卡）返回手牌，支付1资源。"""
        inv = game.state.get_investigator("inv1")
        inv.discard = ["a_glimmer_of_hope_lv0", "some_card",
                       "a_glimmer_of_hope_lv0", "a_glimmer_of_hope_lv0"]
        inv.resources = 5
        impl = AGlimmerOfHope("impl_glimmer")

        assert impl.play_from_discard(game.state, "inv1") is True
        assert inv.hand == ["a_glimmer_of_hope_lv0"] * 3
        assert inv.discard == ["some_card"]
        assert inv.resources == 4

    def test_cannot_play_without_copy_in_discard(self, game):
        inv = game.state.get_investigator("inv1")
        inv.discard = []
        inv.hand = ["a_glimmer_of_hope_lv0"]  # 在手牌中不能经此通道打出
        impl = AGlimmerOfHope("impl_glimmer")
        assert impl.play_from_discard(game.state, "inv1") is False
