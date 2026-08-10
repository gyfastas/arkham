"""Tests for Curiosity (Level 0). (05026)

4+手牌时获得额外[意志][智力]图标（7+时改为2套）。
"""

import pytest

from backend.cards.seeker.curiosity_lv0 import Curiosity
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, Skill
from backend.tests.conftest import (
    make_investigator_data, make_location_data, make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test_curiosity")
    g.chaos_bag.seed(42)
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]
    inv_data = make_investigator_data(intellect=3, willpower=3)
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a")
    g.register_card_data(loc_data)
    g.add_investigator("inv1", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_data)
    g.register_card_data(make_skill_data(
        id="curiosity_lv0", skill_icons={"willpower": 1, "intellect": 1}))
    for i in range(6):
        g.register_card_data(make_skill_data(id=f"filler_{i}", name=f"f{i}"))
    g.card_registry.register_class(Curiosity)
    return g


class TestCuriosity:
    def test_four_cards_in_hand_grants_bonus_icon(self, game):
        """4张手牌（含投入的 curiosity）：智力检定投入时+1图标。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["curiosity_lv0", "filler_0", "filler_1", "filler_2"]
        result = game.skill_test_engine.run_test(
            investigator_id="inv1", skill_type=Skill.INTELLECT,
            difficulty=5, committed_card_ids=["curiosity_lv0"],
        )
        # 基础1（卡面智力图标）+1（4+手牌奖励）= 2 → 3+2+0 = 5 成功
        assert result.committed_icons == 2
        assert result.success is True

    def test_seven_cards_grants_two_bonus_icons(self, game):
        inv = game.state.get_investigator("inv1")
        inv.hand = (["curiosity_lv0"] + [f"filler_{i}" for i in range(6)])
        result = game.skill_test_engine.run_test(
            investigator_id="inv1", skill_type=Skill.WILLPOWER,
            difficulty=6, committed_card_ids=["curiosity_lv0"],
        )
        # 基础1（意志图标）+2（7+手牌奖励）= 3 → 3+3+0 = 6 成功
        assert result.committed_icons == 3
        assert result.success is True

    def test_three_cards_no_bonus(self, game):
        inv = game.state.get_investigator("inv1")
        inv.hand = ["curiosity_lv0", "filler_0", "filler_1"]
        result = game.skill_test_engine.run_test(
            investigator_id="inv1", skill_type=Skill.INTELLECT,
            difficulty=5, committed_card_ids=["curiosity_lv0"],
        )
        assert result.committed_icons == 1
        assert result.success is False
