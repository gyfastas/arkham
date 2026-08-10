"""Tests for Beloved (Level 0)."""

import pytest

from backend.cards.survivor.beloved_lv0 import Beloved
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, Skill
from backend.tests.conftest import (
    make_investigator_data, make_location_data, make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(willpower=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_skill_data(
        id="beloved_lv0",
        skill_icons={"willpower": 1, "agility": 1, "wild": 1}))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(Beloved)
    return g


class TestBeloved:
    def test_card_registered(self, game):
        assert "beloved_lv0" in game.card_registry.registered_cards

    def test_bless_replaced_with_auto_success_and_exiled(self, game):
        """投入后揭示祝福：检定自动成功，本卡移出游戏。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["beloved_lv0"]
        # 祝福+2 → 3+1(投入)+2=6 < 99，必败 → 挚爱翻转为自动成功
        game.chaos_bag.tokens = [ChaosTokenType.BLESS]
        result = game.skill_test_engine.run_test(
            "inv1", Skill.WILLPOWER, 99,
            committed_card_ids=["beloved_lv0"])
        assert result.extra.get("beloved_auto_success") is True
        assert result.success is True
        # 移出游戏（不进弃牌堆）
        assert "beloved_lv0" not in inv.discard
        assert "beloved_lv0" in game.state.scenario.vars["removed_from_game"]

    def test_no_bless_no_effect(self, game):
        """未揭示祝福：正常结算，本卡进弃牌堆。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["beloved_lv0"]
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test(
            "inv1", Skill.WILLPOWER, 99,
            committed_card_ids=["beloved_lv0"])
        assert result.success is False
        assert "beloved_lv0" in inv.discard
        assert "removed_from_game" not in game.state.scenario.vars
