"""Tests for A Watchful Peace (Level 3)."""

import pytest

from backend.cards.survivor.a_watchful_peace_lv3 import AWatchfulPeace
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType
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
        id="a_watchful_peace_lv3", name="A Watchful Peace", cost=1, fast=True))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(AWatchfulPeace)
    return g


def _impl(game):
    impl = AWatchfulPeace("impl_awp")
    impl.bind_chaos_bag(game.chaos_bag)
    return impl


class TestAWatchfulPeace:
    def test_card_registered(self, game):
        assert "a_watchful_peace_lv3" in game.card_registry.registered_cards

    def test_play_returns_5_bless_and_sets_skip_flag(self, game):
        """打出：支付1资源、5个祝福标记返回供应堆、标记跳过遭遇抽取步骤。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["a_watchful_peace_lv3"]
        inv.resources = 3
        game.chaos_bag.tokens = [ChaosTokenType.BLESS] * 4 + [
            ChaosTokenType.ZERO, ChaosTokenType.MINUS_1]
        game.chaos_bag.sealed = [ChaosTokenType.BLESS] * 2  # 袋上封印也计入

        impl = _impl(game)
        assert impl.play(game.state, "inv1") is True

        assert inv.resources == 2
        assert "a_watchful_peace_lv3" in inv.discard
        assert "a_watchful_peace_lv3" not in inv.hand
        # 5个祝福被返回供应堆（袋内4+封印2 中共移除5个）
        remaining = sum(1 for t in game.chaos_bag.tokens
                        if t == ChaosTokenType.BLESS)
        remaining += sum(1 for t in game.chaos_bag.sealed
                         if t == ChaosTokenType.BLESS)
        assert remaining == 1
        assert game.state.scenario.vars["skip_encounter_draw_once"] is True

    def test_play_fails_without_enough_bless(self, game):
        inv = game.state.get_investigator("inv1")
        inv.hand = ["a_watchful_peace_lv3"]
        inv.resources = 3
        game.chaos_bag.tokens = [ChaosTokenType.BLESS] * 3
        game.chaos_bag.sealed = []

        impl = _impl(game)
        assert impl.play(game.state, "inv1") is False
        assert "a_watchful_peace_lv3" in inv.hand
        assert "skip_encounter_draw_once" not in game.state.scenario.vars
