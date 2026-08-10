"""Tests for Butterfly Effect (Level 1)."""

import pytest

from backend.cards.survivor.butterfly_effect_lv1 import ButterflyEffect
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, Skill
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
    make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(willpower=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="butterfly_effect_lv1", name="Butterfly Effect", cost=0, fast=True))
    g.register_card_data(make_skill_data(
        id="guts_like", skill_icons={"willpower": 2}))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(ButterflyEffect)
    impl = ButterflyEffect("impl_butterfly")
    impl.register(g.event_bus, "impl_butterfly")
    return g


class TestButterflyEffect:
    def test_card_registered(self, game):
        assert "butterfly_effect_lv1" in game.card_registry.registered_cards

    def test_symbol_token_returns_committed_card(self, game):
        """揭示符号标记：自动打出，已投入卡牌返回手牌并扣回其图标。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["butterfly_effect_lv1", "guts_like"]
        # 3基础+2图标=5 vs 4；返回 guts_like 后 3 < 4 → 失败
        game.chaos_bag.tokens = [ChaosTokenType.SKULL]
        result = game.skill_test_engine.run_test(
            "inv1", Skill.WILLPOWER, 4,
            committed_card_ids=["guts_like"])
        assert result.modified_skill == 3
        assert result.success is False
        # 蝴蝶效应打出并入弃牌堆
        assert "butterfly_effect_lv1" in inv.discard
        # 被返回的投入卡回到手牌而非弃牌堆
        assert "guts_like" in inv.hand
        assert "guts_like" not in inv.discard

    def test_numeric_token_no_trigger(self, game):
        """数字标记不触发。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["butterfly_effect_lv1", "guts_like"]
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test(
            "inv1", Skill.WILLPOWER, 4,
            committed_card_ids=["guts_like"])
        assert result.success is True
        assert "butterfly_effect_lv1" in inv.hand
        assert "guts_like" in inv.discard  # 正常弃置
