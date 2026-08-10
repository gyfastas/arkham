"""Tests for True Understanding (Level 0).

官方：只能投入冒险卡上打印的能力中的技能检定。如果本次技能检定成功，
发现你所在地点的1个线索。（投入限制由会话层校验，见实现说明。）
"""

import pytest

from backend.cards.seeker.true_understanding_lv0 import TrueUnderstanding
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, Skill
from backend.tests.conftest import (
    make_investigator_data, make_location_data, make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test_true_understanding")
    g.chaos_bag.seed(42)
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]

    inv_data = make_investigator_data(intellect=4)
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a")
    g.register_card_data(loc_data)
    g.add_investigator("player", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_data, clues=2)

    g.register_card_data(make_skill_data(
        id="true_understanding_lv0", skill_icons={"wild": 1}))
    g.card_registry.register_class(TrueUnderstanding)
    return g


class TestTrueUnderstanding:
    def test_success_discovers_clue(self, game):
        """检定成功：发现所在地点1个线索。"""
        inv = game.state.get_investigator("player")
        loc = game.state.get_location("loc_a")
        inv.hand = ["true_understanding_lv0"]
        result = game.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.WILLPOWER,
            difficulty=3, committed_card_ids=["true_understanding_lv0"],
        )
        assert result.success is True
        assert inv.clues == 1
        assert loc.clues == 1
        assert result.extra.get("true_understanding_clue") is True

    def test_failure_no_clue(self, game):
        """检定失败：无线索发现。"""
        game.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]
        inv = game.state.get_investigator("player")
        loc = game.state.get_location("loc_a")
        inv.hand = ["true_understanding_lv0"]
        result = game.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.WILLPOWER,
            difficulty=3, committed_card_ids=["true_understanding_lv0"],
        )
        assert result.success is False
        assert inv.clues == 0
        assert loc.clues == 2
