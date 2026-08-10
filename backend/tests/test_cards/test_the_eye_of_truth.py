"""Tests for The Eye of Truth (Level 5).

官方：如果这次技能检定是诡计卡上的检定且成功，将该诡计卡加入胜利牌区
并叠加真理之眼；叠加期间其图标投入到同名诡计卡的所有检定。
（"诡计卡检定"标记经 scenario.vars 由会话/剧本层传入，见实现说明。）
"""

import pytest

from backend.cards.seeker.the_eye_of_truth_lv5 import TheEyeOfTruth
from backend.engine.game import Game
from backend.models.enums import CardType, ChaosTokenType, Skill
from backend.tests.conftest import (
    make_investigator_data, make_location_data, make_skill_data,
)
from backend.models.state import CardData


@pytest.fixture
def game():
    g = Game("test_eye_of_truth")
    g.chaos_bag.seed(42)
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]

    inv_data = make_investigator_data(willpower=3)
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a")
    g.register_card_data(loc_data)
    g.add_investigator("player", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_data, clues=0)

    g.register_card_data(make_skill_data(
        id="the_eye_of_truth_lv5", skill_icons={"wild": 4}))
    g.register_card_data(CardData(
        id="frozen_in_fear", name="Frozen in Fear", name_cn="恐惧冰封",
        type=CardType.TREACHERY,
    ))
    g.card_registry.register_class(TheEyeOfTruth)
    return g


class TestTheEyeOfTruth:
    def test_treachery_test_success_attaches(self, game):
        """诡计卡检定成功：诡计入胜利牌区，本卡叠加（不进弃牌堆）。"""
        inv = game.state.get_investigator("player")
        inv.hand = ["the_eye_of_truth_lv5"]
        TheEyeOfTruth.mark_treachery_test(game.state, "frozen_in_fear")
        result = game.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.WILLPOWER,
            difficulty=3, committed_card_ids=["the_eye_of_truth_lv5"],
        )
        assert result.success is True
        assert "frozen_in_fear" in game.state.scenario.victory_display
        attached = game.state.scenario.vars.get("eye_of_truth_attached")
        assert attached is not None
        assert attached["treachery_card_id"] == "frozen_in_fear"
        # 叠加出场外：不在弃牌堆
        assert "the_eye_of_truth_lv5" not in inv.discard
        # 叠加期间对同名诡计检定贡献+4
        assert TheEyeOfTruth.attached_icons(game.state, "frozen_in_fear") == 4

    def test_non_treachery_test_no_attach(self, game):
        """非诡计卡检定：无叠加，本卡正常弃置。"""
        inv = game.state.get_investigator("player")
        inv.hand = ["the_eye_of_truth_lv5"]
        result = game.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.WILLPOWER,
            difficulty=3, committed_card_ids=["the_eye_of_truth_lv5"],
        )
        assert result.success is True
        assert game.state.scenario.victory_display == []
        assert game.state.scenario.vars.get("eye_of_truth_attached") is None
        assert "the_eye_of_truth_lv5" in inv.discard
