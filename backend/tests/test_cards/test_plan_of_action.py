"""Tests for Plan of Action (Level 0).

官方：第一行动中或之前的检定：本卡获得[willpower][agility]；第一与第三
行动之间且成功：抽1张牌；第三行动中或之后：获得[combat][intellect]。
（实现按已完成行动数分档：0→条款1，1→条款2，≥2→条款3。）
"""

import pytest

from backend.cards.seeker.plan_of_action_lv0 import PlanOfAction
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, Skill
from backend.tests.conftest import (
    make_investigator_data, make_location_data, make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test_plan_of_action")
    g.chaos_bag.seed(42)
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]

    inv_data = make_investigator_data(
        willpower=3, intellect=3, combat=3, agility=3)
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a")
    g.register_card_data(loc_data)
    g.add_investigator(
        "player", inv_data, deck=["card_a"], starting_location="loc_a")
    g.add_location("loc_a", loc_data, clues=0)

    g.register_card_data(make_skill_data(
        id="plan_of_action_lv0", skill_icons={"wild": 1}))
    g.card_registry.register_class(PlanOfAction)
    return g


class TestPlanOfAction:
    def test_first_action_grants_willpower_agility_icons(self, game):
        """条款1（已完成0行动）：意志检定获得额外+1（wild1+willpower图标）。"""
        inv = game.state.get_investigator("player")
        inv.actions_remaining = 3  # 尚未执行行动
        result = game.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.WILLPOWER,
            difficulty=5, committed_card_ids=["plan_of_action_lv0"],
        )
        # 3 + 1(wild) + 1(获得的意志图标) = 5
        assert result.committed_icons == 2
        assert result.success is True

    def test_first_action_icons_do_not_help_other_skills(self, game):
        """条款1的[willpower][agility]图标对智力检定无加值。"""
        inv = game.state.get_investigator("player")
        inv.actions_remaining = 3
        result = game.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.INTELLECT,
            difficulty=5, committed_card_ids=["plan_of_action_lv0"],
        )
        assert result.committed_icons == 1  # 仅wild
        assert result.success is False  # 3+1=4 < 5

    def test_middle_clause_draws_on_success(self, game):
        """条款2（已完成1行动）：成功抽1张牌。"""
        inv = game.state.get_investigator("player")
        inv.actions_remaining = 2  # 已完成1个行动
        inv.hand = ["plan_of_action_lv0"]
        result = game.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.INTELLECT,
            difficulty=4, committed_card_ids=["plan_of_action_lv0"],
        )
        assert result.success is True
        assert "card_a" in inv.hand
        assert result.extra.get("plan_of_action_drew") is True

    def test_third_action_grants_combat_intellect_icons(self, game):
        """条款3（已完成≥2行动）：战斗检定获得额外+1。"""
        inv = game.state.get_investigator("player")
        inv.actions_remaining = 1  # 已完成2个行动（第三行动中）
        result = game.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.COMBAT,
            difficulty=5, committed_card_ids=["plan_of_action_lv0"],
        )
        assert result.committed_icons == 2
        assert result.success is True
