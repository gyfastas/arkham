"""Tests for Last Chance (Level 0)."""

import pytest
from backend.cards.survivor.last_chance_lv0 import LastChance
from backend.models.enums import ChaosTokenType, PlayerClass, Skill
from backend.tests.conftest import (
    make_investigator_data, make_location_data, make_skill_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_skill_data(
        id="last_chance_lv0", name="Last Chance",
        card_class=PlayerClass.SURVIVOR, skill_icons={"wild": 5}))
    g.register_card_data(make_skill_data(id="filler", skill_icons={}))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(LastChance)
    return g


def _commit_last_chance(game, hand_size):
    inv = game.state.get_investigator("inv1")
    inv.hand = ["last_chance_lv0"] + ["filler"] * (hand_size - 1)
    game.chaos_bag.tokens = [ChaosTokenType.ZERO]
    return game.skill_test_engine.run_test(
        "inv1", Skill.COMBAT, 99, committed_card_ids=["last_chance_lv0"])


class TestLastChance:
    def test_card_registered(self, game):
        assert "last_chance_lv0" in game.card_registry.registered_cards

    def test_icons_shrink_with_hand_size(self, game):
        """手牌每张 -1 万能图标（投入时本卡仍在手牌，计入自身）。"""
        # 手牌1张（仅孤注一掷）：5-1=4 图标
        result = _commit_last_chance(game, hand_size=1)
        assert result.committed_icons == 4

    def test_icons_with_three_cards_in_hand(self, game):
        result = _commit_last_chance(game, hand_size=3)
        assert result.committed_icons == 2

    def test_icons_floor_at_zero(self, game):
        """手牌≥5时图标归0（不为负、不倒扣基础值）。"""
        result = _commit_last_chance(game, hand_size=6)
        assert result.committed_icons == 0
        assert result.modified_skill == 3  # 战斗3+标记0，不被扣成负数
