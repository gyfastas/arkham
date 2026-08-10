"""Tests for Calvin Wright investigator ability."""

import pytest
from backend.cards.survivor.calvin_wright import CalvinWright
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, Skill
from backend.tests.conftest import (
    make_investigator_data, make_location_data,
)


def _make_game():
    g = Game("test_calvin")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(
        id="calvin_wright", name="Calvin Wright",
        willpower=0, intellect=0, combat=0, agility=0,
        health=6, sanity=6,
    )
    g.register_card_data(inv_data)
    loc_data = make_location_data()
    g.register_card_data(loc_data)

    g.add_investigator("calvin", inv_data, deck=["filler"] * 10,
                       starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)
    return g


def _impl(g):
    return g.card_registry.active_instances["investigator_calvin"]


class TestSetupActivation:
    def test_setup_activates_impl(self):
        g = _make_game()
        g.setup()
        assert isinstance(_impl(g), CalvinWright)


class TestSkillBonus:
    def test_skill_bonuses_from_damage_and_horror(self):
        """每点恐惧+1意志/+1智力；每点伤害+1战斗/+1敏捷。"""
        g = _make_game()
        g.setup()
        inv = g.state.get_investigator("calvin")
        inv.damage = 2
        inv.horror = 3

        bonuses = g.preview_skill_bonuses("calvin")
        assert bonuses == {
            "willpower": 3, "intellect": 3, "combat": 2, "agility": 2,
        }

    def test_bonus_applies_in_skill_test(self):
        """实际检定中生效：0意志+3恐惧 vs 难度3 成功。"""
        g = _make_game()
        g.setup()
        inv = g.state.get_investigator("calvin")
        inv.horror = 3

        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = g.skill_test_engine.run_test(
            investigator_id="calvin", skill_type=Skill.WILLPOWER, difficulty=3,
        )
        assert result.modified_skill == 3
        assert result.success is True

    def test_no_bonus_when_unscathed(self):
        """无伤害无恐惧时无加值。"""
        g = _make_game()
        g.setup()
        assert g.preview_skill_bonuses("calvin") == {}


class TestElderSign:
    def test_default_heals_damage_first(self):
        """远古印记缺省：有伤害先治愈1伤害。"""
        g = _make_game()
        g.setup()
        inv = g.state.get_investigator("calvin")
        inv.damage = 2
        inv.horror = 3

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = g.skill_test_engine.run_test(
            investigator_id="calvin", skill_type=Skill.WILLPOWER, difficulty=99,
        )
        assert result.token_modifier == 0  # +0
        assert inv.damage == 1
        assert inv.horror == 3

    def test_default_heals_horror_when_no_damage(self):
        """缺省：无伤害时治愈1恐惧。"""
        g = _make_game()
        g.setup()
        inv = g.state.get_investigator("calvin")
        inv.horror = 2

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        g.skill_test_engine.run_test(
            investigator_id="calvin", skill_type=Skill.WILLPOWER, difficulty=99,
        )
        assert inv.horror == 1

    def test_preset_take_direct_damage(self):
        """预设 take_damage：受1直接伤害（并反过来提升战斗/敏捷）。"""
        g = _make_game()
        g.setup()
        inv = g.state.get_investigator("calvin")
        g.state.scenario.vars["calvin_wright_elder_choice"] = "take_damage"

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        g.skill_test_engine.run_test(
            investigator_id="calvin", skill_type=Skill.WILLPOWER, difficulty=99,
        )
        assert inv.damage == 1
        bonuses = g.preview_skill_bonuses("calvin")
        assert bonuses["combat"] == 1 and bonuses["agility"] == 1

    def test_preset_take_direct_horror(self):
        """预设 take_horror：受1直接恐惧。"""
        g = _make_game()
        g.setup()
        inv = g.state.get_investigator("calvin")
        g.state.scenario.vars["calvin_wright_elder_choice"] = "take_horror"

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        g.skill_test_engine.run_test(
            investigator_id="calvin", skill_type=Skill.WILLPOWER, difficulty=99,
        )
        assert inv.horror == 1

    def test_no_heal_below_zero(self):
        """无伤害无恐惧时缺省不结算，不出负值。"""
        g = _make_game()
        g.setup()
        inv = g.state.get_investigator("calvin")

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        g.skill_test_engine.run_test(
            investigator_id="calvin", skill_type=Skill.WILLPOWER, difficulty=99,
        )
        assert inv.damage == 0 and inv.horror == 0
