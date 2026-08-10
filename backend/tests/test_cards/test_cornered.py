"""Tests for Cornered (Level 2)."""

import pytest

from backend.cards.survivor.cornered_lv2 import Cornered
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, Skill
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="cornered_lv2", name="Cornered", cost=2, traits=["talent"]))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(Cornered)
    return g


def _play_cornered(game):
    inv = game.state.get_investigator("inv1")
    inv.resources = 5
    inv.hand = ["cornered_lv2"]
    assert game.action_resolver.perform_action(
        "inv1", Action.PLAY, card_id="cornered_lv2") is True
    iid = next(i for i in inv.play_area
               if game.state.get_card_instance(i).card_id == "cornered_lv2")
    return inv, iid, game.card_registry.active_instances[iid]


class TestCornered:
    def test_card_registered(self, game):
        assert "cornered_lv2" in game.card_registry.registered_cards

    def test_discard_card_for_plus_2(self, game):
        """丢弃1张手牌：本次检定+2技能值。"""
        inv, iid, impl = _play_cornered(game)
        inv.hand = ["fodder_card"]
        assert impl.spend(game.state, "inv1") is True
        assert "fodder_card" in inv.discard

        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test("inv1", Skill.INTELLECT, 5)
        assert result.modified_skill == 5
        assert result.success is True

    def test_limit_once_per_test(self, game):
        """每次检定限1次；检定结束后可再次使用。"""
        inv, iid, impl = _play_cornered(game)
        inv.hand = ["card_a", "card_b"]
        assert impl.spend(game.state, "inv1") is True
        assert impl.spend(game.state, "inv1") is False

        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        game.skill_test_engine.run_test("inv1", Skill.INTELLECT, 1)

        inv.hand = ["card_c"]
        assert impl.spend(game.state, "inv1") is True
        assert "card_c" in inv.discard
