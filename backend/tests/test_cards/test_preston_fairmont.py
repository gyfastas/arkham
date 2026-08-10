"""Tests for Preston Fairmont investigator ability."""

import pytest
from backend.cards.rogue.preston_fairmont import PrestonFairmont
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_investigator_data, make_location_data,
)


def _make_game():
    g = Game("test_preston")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="preston_fairmont",
                                      name="Preston Fairmont", willpower=1)
    g.register_card_data(inv_data)
    loc_data = make_location_data()
    g.register_card_data(loc_data)

    g.add_investigator("preston", inv_data, deck=["filler"] * 10,
                       starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)
    return g


def _impl(g):
    return g.card_registry.active_instances["investigator_preston"]


def _add_inheritance(g, resources=0):
    inst = CardInstance(
        instance_id="fi_1", card_id="family_inheritance_lv0",
        owner_id="preston", controller_id="preston",
    )
    inst.uses["resources"] = resources
    g.state.cards_in_play["fi_1"] = inst
    g.state.get_investigator("preston").play_area.append("fi_1")
    return inst


class TestSetupActivation:
    def test_setup_activates_impl(self):
        g = _make_game()
        g.setup()
        assert isinstance(_impl(g), PrestonFairmont)


class TestRedirectGain:
    def test_card_effect_gain_goes_to_family_inheritance(self):
        """卡牌效果获得的资源放到家族遗产上，而非资源池。"""
        g = _make_game()
        g.setup()
        impl = _impl(g)
        inv = g.state.get_investigator("preston")
        inst = _add_inheritance(g, resources=2)
        inv.resources = 5

        assert impl.redirect_gain(g.state, "preston", 3) is True
        assert inst.uses["resources"] == 5
        assert inv.resources == 5  # 资源池不变

    def test_fallback_to_pool_without_inheritance(self):
        """家族遗产未入场：回退资源池并返回 False。"""
        g = _make_game()
        g.setup()
        impl = _impl(g)
        inv = g.state.get_investigator("preston")
        inv.resources = 5

        assert impl.redirect_gain(g.state, "preston", 3) is False
        assert inv.resources == 8


class TestElderSignAutoSuccess:
    def test_spend_2_to_auto_succeed_pool_only(self):
        """远古印记：资源池有2资源时自动花费并自动成功。"""
        g = _make_game()
        g.setup()
        inv = g.state.get_investigator("preston")
        inv.resources = 3

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = g.skill_test_engine.run_test(
            investigator_id="preston", skill_type=Skill.WILLPOWER, difficulty=99,
        )
        assert result.success is True
        assert inv.resources == 1

    def test_spend_2_split_pool_and_inheritance(self):
        """资源池不足时差额从家族遗产扣。"""
        g = _make_game()
        g.setup()
        inv = g.state.get_investigator("preston")
        inst = _add_inheritance(g, resources=1)
        inv.resources = 1

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = g.skill_test_engine.run_test(
            investigator_id="preston", skill_type=Skill.WILLPOWER, difficulty=99,
        )
        assert result.success is True
        assert inv.resources == 0
        assert inst.uses["resources"] == 0

    def test_no_auto_success_when_unaffordable(self):
        """可花费资源不足2：不触发自动成功，资源不动。"""
        g = _make_game()
        g.setup()
        inv = g.state.get_investigator("preston")
        inv.resources = 1

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = g.skill_test_engine.run_test(
            investigator_id="preston", skill_type=Skill.WILLPOWER, difficulty=99,
        )
        assert result.success is False
        assert inv.resources == 1

    def test_decline_via_scenario_var(self):
        """预设放弃：不花费也不翻转结果。"""
        g = _make_game()
        g.setup()
        inv = g.state.get_investigator("preston")
        inv.resources = 5
        g.state.scenario.vars["preston_fairmont_decline_auto_success"] = True

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = g.skill_test_engine.run_test(
            investigator_id="preston", skill_type=Skill.WILLPOWER, difficulty=99,
        )
        assert result.success is False
        assert inv.resources == 5

    def test_auto_success_only_for_own_elder_sign(self):
        """其他调查员的远古印记不触发普雷斯顿的花费。"""
        g = _make_game()
        other_data = make_investigator_data(id="other_inv", name="Other")
        g.register_card_data(other_data)
        g.add_investigator("other", other_data, deck=["filler"] * 10,
                           starting_location="test_location")
        g.setup()
        inv = g.state.get_investigator("preston")
        inv.resources = 5

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        g.skill_test_engine.run_test(
            investigator_id="other", skill_type=Skill.WILLPOWER, difficulty=99,
        )
        assert inv.resources == 5
