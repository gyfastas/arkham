"""Tests for Essence of the Dream (Level 0)."""

import pytest
from backend.cards.seeker.essence_of_the_dream_lv0 import EssenceOfTheDream
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
    essence = make_skill_data(
        id="essence_of_the_dream_lv0", name="Essence of the Dream",
        skill_icons={"wild": 2},
    )
    g.register_card_data(essence)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=0)
    g.card_registry.register_class(EssenceOfTheDream)
    return g


class TestEssenceOfTheDream:
    def test_set_aside_instead_of_discard_after_commit(self, game):
        """投入检定后：不进入弃牌堆，改为放在一边（场外）。"""
        inv = game.state.get_investigator("inv1")
        inv.hand.append("essence_of_the_dream_lv0")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        result = game.skill_test_engine.run_test(
            "inv1", Skill.INTELLECT, difficulty=1,
            committed_card_ids=["essence_of_the_dream_lv0"],
        )
        assert result.success is True
        assert "essence_of_the_dream_lv0" not in inv.discard
        assert "essence_of_the_dream_lv0" not in inv.hand
        assert game.state.scenario.vars["set_aside"] == ["essence_of_the_dream_lv0"]

    def test_wild_icons_still_count(self, game):
        """投入时2个万能图标正常计入。"""
        inv = game.state.get_investigator("inv1")
        inv.hand.append("essence_of_the_dream_lv0")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        result = game.skill_test_engine.run_test(
            "inv1", Skill.INTELLECT, difficulty=6,
            committed_card_ids=["essence_of_the_dream_lv0"],
        )
        # 智力4 + 2万能 + 0 = 6，恰好成功
        assert result.committed_icons == 2
        assert result.success is True
