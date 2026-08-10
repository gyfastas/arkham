"""Tests for Against All Odds (Level 2)."""

import pytest

from backend.cards.survivor.against_all_odds_lv2 import AgainstAllOdds
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, Skill
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)


class _ScriptedBag:
    """按序返回标记的伪袋：让"额外揭示"的抽取在测试中确定。"""

    def __init__(self, tokens):
        self.tokens = list(tokens)
        self.sealed = []

    def draw(self):
        return self.tokens.pop(0)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="against_all_odds_lv2", name="Against All Odds", cost=2, fast=True))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(AgainstAllOdds)
    impl = AgainstAllOdds("impl_aao")
    impl.register(g.event_bus, "impl_aao")
    g._aao_impl = impl
    return g


class TestAgainstAllOdds:
    def test_card_registered(self, game):
        assert "against_all_odds_lv2" in game.card_registry.registered_cards

    def test_extra_tokens_rescue_auto_fail(self, game):
        """难度>基础技能值：额外揭示X个标记并选最优（放弃自动失败）。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["against_all_odds_lv2"]
        inv.resources = 5
        # 原标记必为自动失败；额外揭示（X=难度4-基础3=1）为+1 → 选+1
        game.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]
        game._aao_impl.bind_chaos_bag(_ScriptedBag([ChaosTokenType.PLUS_1]))

        result = game.skill_test_engine.run_test("inv1", Skill.COMBAT, 4)
        assert result.auto_fail is False
        assert result.token_modifier == 1
        assert result.success is True  # 3基础 + 1 = 4 ≥ 4
        assert "against_all_odds_lv2" in inv.discard
        assert inv.resources == 3

    def test_keeps_original_when_it_is_best(self, game):
        """原标记最优时保持不变（额外标记被忽略）。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["against_all_odds_lv2"]
        inv.resources = 5
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]
        game._aao_impl.bind_chaos_bag(_ScriptedBag([ChaosTokenType.AUTO_FAIL]))

        result = game.skill_test_engine.run_test("inv1", Skill.COMBAT, 4)
        assert result.auto_fail is False
        assert result.token_modifier == 1
        assert result.success is True

    def test_no_trigger_when_difficulty_not_above_base(self, game):
        """难度≤基础技能值：不打出。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["against_all_odds_lv2"]
        inv.resources = 5
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test("inv1", Skill.COMBAT, 2)
        assert result.success is True
        assert "against_all_odds_lv2" in inv.hand
        assert inv.resources == 5
