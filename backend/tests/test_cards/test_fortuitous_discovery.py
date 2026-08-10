"""Tests for Fortuitous Discovery (Level 0)."""

import pytest

from backend.cards.survivor.fortuitous_discovery_lv0 import FortuitousDiscovery
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)
    loc = make_location_data(shroud=2, clue_value=5)
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="fortuitous_discovery_lv0", name="Fortuitous Discovery", cost=0))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=5)
    g.card_registry.register_class(FortuitousDiscovery)
    return g


class TestFortuitousDiscovery:
    def test_card_registered(self, game):
        assert "fortuitous_discovery_lv0" in \
            game.card_registry.registered_cards

    def test_x_bonus_and_extra_clues(self, game):
        """弃牌堆2张副本：调查+2智力，成功额外发现2个线索。"""
        inv = game.state.get_investigator("inv1")
        inv.resources = 3
        inv.discard = ["fortuitous_discovery_lv0", "fortuitous_discovery_lv0"]
        inv.hand = ["fortuitous_discovery_lv0"]

        assert game.action_resolver.perform_action(
            "inv1", Action.PLAY,
            card_id="fortuitous_discovery_lv0") is True
        assert inv.active_effects["fortuitous_discovery_lv0"]["x"] == 2

        game.chaos_bag.tokens = [ChaosTokenType.ZERO]  # 3+2=5 vs 2 成功
        assert game.action_resolver.perform_action(
            "inv1", Action.INVESTIGATE) is True
        # 引擎1个 + 卡面额外2个
        assert inv.clues == 3
        assert game.state.get_location("test_location").clues == 2

    def test_no_copies_no_bonus(self, game):
        """弃牌堆无副本：X=0，仅正常调查。"""
        inv = game.state.get_investigator("inv1")
        inv.resources = 3
        inv.hand = ["fortuitous_discovery_lv0"]
        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="fortuitous_discovery_lv0")
        assert inv.active_effects["fortuitous_discovery_lv0"]["x"] == 0

        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        game.action_resolver.perform_action("inv1", Action.INVESTIGATE)
        assert inv.clues == 1
