"""Tests for Leadership (Level 2). (06235)

投入到他人检定时获得额外[意志][wild]；成功后持有者+2资源，
投入他人检定时执行者也+2。
"""

import pytest
from backend.cards.guardian.leadership_lv2 import Leadership
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, PlayerClass, Skill
from backend.tests.conftest import (
    make_investigator_data, make_location_data, make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    inv_data2 = make_investigator_data(id="inv2_card", name="Second")
    g.register_card_data(inv_data2)
    g.register_card_data(make_location_data())
    g.register_card_data(make_skill_data(
        id="leadership_lv2", name="Leadership",
        card_class=PlayerClass.GUARDIAN, skill_icons={"wild": 1},
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_investigator("inv2", inv_data2, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=0)
    g.card_registry.register_class(Leadership)
    return g


class TestLeadership:
    def test_committed_to_others_test(self, game):
        """投入他人检定：+3图标（1 wild + 2 额外）；双方各+2资源；卡从持有者手牌弃置。"""
        inv1 = game.state.get_investigator("inv1")
        inv2 = game.state.get_investigator("inv2")
        inv1.hand = ["leadership_lv2"]
        inv1.resources = 0
        inv2.resources = 0
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        result = game.skill_test_engine.run_test(
            investigator_id="inv2",
            skill_type=Skill.WILLPOWER,
            difficulty=2,
            committed_card_ids=["leadership_lv2"],
        )
        assert result.success is True
        assert result.committed_icons == 3  # 1 wild + 2 额外
        assert inv1.resources == 2
        assert inv2.resources == 2
        # 从持有者（非执行者）手牌弃置
        assert "leadership_lv2" not in inv1.hand
        assert "leadership_lv2" in inv1.discard

    def test_committed_to_own_test(self, game):
        """投入自己的检定：无额外图标；仅自己+2资源。"""
        inv1 = game.state.get_investigator("inv1")
        inv1.hand = ["leadership_lv2"]
        inv1.resources = 0
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        result = game.skill_test_engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.WILLPOWER,
            difficulty=2,
            committed_card_ids=["leadership_lv2"],
        )
        assert result.success is True
        assert result.committed_icons == 1  # 仅卡面 wild
        assert inv1.resources == 2
        assert "leadership_lv2" in inv1.discard
