"""Tests for Fey (Level 1)."""

import pytest
from backend.cards.seeker.fey_lv1 import Fey
from backend.engine.game import Game
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, Skill
from backend.tests.conftest import make_investigator_data, make_location_data, make_skill_data


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag = ChaosBag()
    g.chaos_bag.seed(42)
    g.skill_test_engine.chaos_bag = g.chaos_bag

    inv_data = make_investigator_data(intellect=4)
    g.register_card_data(inv_data)
    loc_data = make_location_data()
    g.register_card_data(loc_data)
    fey = make_skill_data(
        id="fey_lv1", name="Fey", skill_icons={"willpower": 1, "wild": 2},
    )
    g.register_card_data(fey)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=0)
    g.card_registry.register_class(Fey)
    return g


class TestFey:
    def test_returns_to_hand_when_curse_revealed(self, game):
        """检定中揭示诅咒标记：检定结束时返回手牌而非弃牌堆。"""
        inv = game.state.get_investigator("inv1")
        inv.hand.append("fey_lv1")
        game.chaos_bag.tokens = [ChaosTokenType.CURSE]

        result = game.skill_test_engine.run_test(
            "inv1", Skill.INTELLECT, difficulty=2,
            committed_card_ids=["fey_lv1"],
        )
        # 智力4 + 2万能 - 2诅咒 = 4 ≥ 2 成功
        assert result.success is True
        assert "fey_lv1" in inv.hand
        assert "fey_lv1" not in inv.discard

    def test_discarded_normally_without_curse(self, game):
        """未揭示诅咒标记：正常进入弃牌堆。"""
        inv = game.state.get_investigator("inv1")
        inv.hand.append("fey_lv1")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        result = game.skill_test_engine.run_test(
            "inv1", Skill.INTELLECT, difficulty=2,
            committed_card_ids=["fey_lv1"],
        )
        assert result.success is True
        assert "fey_lv1" not in inv.hand
        assert "fey_lv1" in inv.discard
