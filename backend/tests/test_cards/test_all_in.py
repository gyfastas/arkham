"""Tests for All In (Level 5)."""

import pytest
from backend.cards.rogue.all_in_lv5 import AllIn
from backend.engine.game import Game
from backend.models.enums import CardType, ChaosTokenType, PlayerClass, Skill
from backend.models.state import CardData
from backend.tests.conftest import (
    make_investigator_data, make_location_data, make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(willpower=4)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_skill_data(
        id="all_in_lv5", name="All In", card_class=PlayerClass.ROGUE,
        skill_icons={"wild": 2},
    ))
    g.register_card_data(make_skill_data(
        id="fodder", name="Fodder", card_class=PlayerClass.ROGUE,
    ))
    g.register_card_data(CardData(
        id="weak_x", name="Weakness", name_cn="弱点", type=CardType.TREACHERY,
        card_class=PlayerClass.NEUTRAL, subtype="weakness",
    ))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(AllIn)
    return g


class TestAllIn:
    def test_draw_per_margin_capped_at_5(self, game):
        """成功：每超出1点抽1张，至多5张。"""
        inv = game.state.get_investigator("inv1")
        inv.hand.append("all_in_lv5")
        inv.deck = ["fodder"] * 8
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]

        result = game.skill_test_engine.run_test(
            "inv1", Skill.WILLPOWER, 1,
            committed_card_ids=["all_in_lv5"],
        )
        assert result.success is True
        # 4 + 2(图标) + 1(标记) - 1 = 超出6 → 抽5
        assert result.extra.get("all_in_drawn") == 5
        assert inv.hand == ["fodder"] * 5  # all_in 已在 ST.8 弃置
        assert "all_in_lv5" in inv.discard

    def test_weakness_shuffled_back_unresolved(self, game):
        """抽到的弱点洗回牌堆，不入手中也不结算。"""
        inv = game.state.get_investigator("inv1")
        inv.hand.append("all_in_lv5")
        inv.deck = ["weak_x", "fodder", "fodder", "fodder"]
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        result = game.skill_test_engine.run_test(
            "inv1", Skill.WILLPOWER, 1,
            committed_card_ids=["all_in_lv5"],
        )
        # 4+2+0-1=5 → 抽5，牌堆仅4张：第1张是弱点
        assert result.extra.get("all_in_weaknesses_returned") == 1
        assert result.extra.get("all_in_drawn") == 3
        assert "weak_x" not in inv.hand
        assert "weak_x" in inv.deck  # 洗回牌堆
        assert "weak_x" not in inv.discard

    def test_no_draw_on_failure(self, game):
        inv = game.state.get_investigator("inv1")
        inv.hand.append("all_in_lv5")
        inv.deck = ["fodder"] * 4
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_3]

        result = game.skill_test_engine.run_test(
            "inv1", Skill.WILLPOWER, 5,
            committed_card_ids=["all_in_lv5"],
        )
        assert result.success is False
        assert "all_in_drawn" not in result.extra
        assert inv.deck == ["fodder"] * 4
