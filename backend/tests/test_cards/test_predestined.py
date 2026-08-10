"""Tests for Predestined (Level 0)."""

import pytest
from backend.cards.survivor.predestined_lv0 import Predestined
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
        id="predestined_lv0", name="Predestined",
        card_class=PlayerClass.SURVIVOR, skill_icons={}))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(Predestined)
    return g


def _count(game, token):
    return sum(1 for t in game.chaos_bag.tokens if t == token)


def _fail_test(game):
    inv = game.state.get_investigator("inv1")
    inv.hand = ["predestined_lv0"]
    # 战斗3 vs 难度5 → 失败
    return game.skill_test_engine.run_test(
        "inv1", Skill.COMBAT, 5, committed_card_ids=["predestined_lv0"])


class TestPredestined:
    def test_card_registered(self, game):
        assert "predestined_lv0" in game.card_registry.registered_cards

    def test_failed_test_removes_curses(self, game):
        """检定失败：袋中有诅咒时移除至多2个。"""
        game.chaos_bag.tokens = [ChaosTokenType.CURSE, ChaosTokenType.CURSE,
                                 ChaosTokenType.CURSE, ChaosTokenType.ZERO]
        result = _fail_test(game)

        assert result.success is False
        assert _count(game, ChaosTokenType.CURSE) == 1
        assert _count(game, ChaosTokenType.BLESS) == 0

    def test_failed_test_adds_bless_when_no_curses(self, game):
        """检定失败：袋中无诅咒时加入2个祝福。"""
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = _fail_test(game)

        assert result.success is False
        assert _count(game, ChaosTokenType.BLESS) == 2

    def test_no_effect_on_success(self, game):
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]
        inv = game.state.get_investigator("inv1")
        inv.hand = ["predestined_lv0"]
        # 战斗3+1 vs 难度2 → 成功
        result = game.skill_test_engine.run_test(
            "inv1", Skill.COMBAT, 2, committed_card_ids=["predestined_lv0"])

        assert result.success is True
        assert _count(game, ChaosTokenType.BLESS) == 0
