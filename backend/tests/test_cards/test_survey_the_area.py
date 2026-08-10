"""Tests for Survey the Area (Level 1).

官方：只要地区勘测在你手中或被投入到技能检定中，其获得等于你[agility]
的[intellect]图标，以及等于你[intellect]的[agility]图标。
"""

import pytest

from backend.cards.seeker.survey_the_area_lv1 import SurveyTheArea
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, Skill
from backend.tests.conftest import (
    make_investigator_data, make_location_data, make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test_survey_the_area")
    g.chaos_bag.seed(42)
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]

    inv_data = make_investigator_data(intellect=2, agility=5)
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a")
    g.register_card_data(loc_data)
    g.add_investigator("player", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_data, clues=0)

    # make_skill_data 会把空 icons 换成默认 wild，这里直接构造空图标卡
    from backend.models.enums import CardType, PlayerClass
    from backend.models.state import CardData
    g.register_card_data(CardData(
        id="survey_the_area_lv1", name="Survey the Area",
        name_cn="地区勘测", type=CardType.SKILL,
        card_class=PlayerClass.SEEKER, skill_icons={},
    ))
    g.card_registry.register_class(SurveyTheArea)
    return g


class TestSurveyTheArea:
    def test_intellect_test_gains_agility_icons(self, game):
        """智力检定：+你敏捷值（2智力+5敏捷图标=7过难度6）。"""
        result = game.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.INTELLECT,
            difficulty=6, committed_card_ids=["survey_the_area_lv1"],
        )
        assert result.committed_icons == 5
        assert result.success is True

    def test_agility_test_gains_intellect_icons(self, game):
        """敏捷检定：+你智力值（5敏捷+2智力图标=7过难度6）。"""
        result = game.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.AGILITY,
            difficulty=6, committed_card_ids=["survey_the_area_lv1"],
        )
        assert result.committed_icons == 2
        assert result.success is True

    def test_other_skills_get_nothing(self, game):
        """其它检定（意志）：不加图标。"""
        result = game.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.WILLPOWER,
            difficulty=3, committed_card_ids=["survey_the_area_lv1"],
        )
        assert result.committed_icons == 0
