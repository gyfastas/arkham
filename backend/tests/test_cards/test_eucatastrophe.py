"""Tests for Eucatastrophe (Level 3)."""

import pytest
from backend.cards.survivor.eucatastrophe_lv3 import Eucatastrophe
from backend.models.enums import ChaosTokenType, PlayerClass, Skill
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data(willpower=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(id="eucatastrophe_lv3", cost=2, fast=True))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(Eucatastrophe)
    return g


def _arm(game):
    """模拟手牌中的事件：登记实现并把卡放进手牌。"""
    impl = Eucatastrophe("impl_eucatastrophe")
    impl.register(game.event_bus, "impl_eucatastrophe")
    inv = game.state.get_investigator("inv1")
    inv.hand = ["eucatastrophe_lv3"]
    inv.resources = 2
    return inv


class TestEucatastrophe:
    def test_card_registered(self, game):
        assert "eucatastrophe_lv3" in game.card_registry.registered_cards

    def test_cancels_token_that_would_reduce_skill_to_zero(self, game):
        """意志3 + 标记-5 → 技能值将降为0：取消标记视为远古印记（修正0）。"""
        inv = _arm(game)
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_5]

        result = game.skill_test_engine.run_test("inv1", Skill.WILLPOWER, 3)

        assert result.token_modifier == 0
        assert result.modified_skill == 3
        assert result.success is True
        assert "eucatastrophe_lv3" in inv.discard
        assert inv.resources == 0

    def test_no_trigger_when_skill_stays_above_zero(self, game):
        """标记不会把技能值降为0时不打出。"""
        inv = _arm(game)
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_1]

        result = game.skill_test_engine.run_test("inv1", Skill.WILLPOWER, 3)

        assert result.token_modifier == -1
        assert result.success is False
        assert "eucatastrophe_lv3" in inv.hand
        assert inv.resources == 2

    def test_cancels_auto_fail_token(self, game):
        """自动失败标记：视为远古印记，按修正0重算成败。"""
        inv = _arm(game)
        game.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]

        result = game.skill_test_engine.run_test("inv1", Skill.WILLPOWER, 2)

        assert result.success is True  # 3 + 0 >= 2
        assert "eucatastrophe_lv3" in inv.discard
        assert inv.resources == 0

    def test_auto_fail_save_can_still_fail(self, game):
        """自动失败被取消后，技能值不足仍然失败。"""
        inv = _arm(game)
        game.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]

        result = game.skill_test_engine.run_test("inv1", Skill.WILLPOWER, 5)

        assert result.success is False  # 3 + 0 < 5
        assert "eucatastrophe_lv3" in inv.discard

    def test_no_trigger_without_resources(self, game):
        inv = _arm(game)
        inv.resources = 0
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_5]

        result = game.skill_test_engine.run_test("inv1", Skill.WILLPOWER, 3)

        assert result.token_modifier == -5
        assert result.success is False
        assert "eucatastrophe_lv3" in inv.hand
