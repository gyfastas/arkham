"""Tests for Cunning (Level 0)."""

import pytest
from backend.cards.rogue.cunning_lv0 import Cunning
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, PlayerClass, Skill
from backend.tests.conftest import (
    make_investigator_data, make_location_data, make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(intellect=3, combat=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_skill_data(
        id="cunning_lv0", name="Cunning", card_class=PlayerClass.ROGUE,
        skill_icons={"intellect": 1, "agility": 1},
    ))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(Cunning)
    return g


def _run(game, skill, difficulty, resources):
    inv = game.state.get_investigator("inv1")
    inv.resources = resources
    inv.hand = ["cunning_lv0"]
    game.chaos_bag.tokens = [ChaosTokenType.ZERO]
    return game.skill_test_engine.run_test(
        "inv1", skill, difficulty, committed_card_ids=["cunning_lv0"],
    )


class TestCunning:
    def test_below_5_resources_no_bonus(self, game):
        """资源不足5：仅印刷图标（智力检定计[智力]1）。"""
        result = _run(game, Skill.INTELLECT, 3, resources=4)
        assert result.modified_skill == 3 + 1

    def test_5_resources_gain_two_icons(self, game):
        """5+资源：额外[智力][敏捷] → 智力检定再+2。"""
        result = _run(game, Skill.INTELLECT, 3, resources=5)
        assert result.modified_skill == 3 + 1 + 2

    def test_10_resources_gain_four_icons(self, game):
        """10+资源：额外[智力][智力][敏捷][敏捷] → 智力检定再+4。"""
        result = _run(game, Skill.INTELLECT, 3, resources=10)
        assert result.modified_skill == 3 + 1 + 4

    def test_no_bonus_on_other_skills(self, game):
        """获得的图标为智力/敏捷：战斗检定无加成（印刷图标同样不计）。"""
        result = _run(game, Skill.COMBAT, 3, resources=10)
        assert result.modified_skill == 3
