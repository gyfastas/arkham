"""Tests for Carolyn Fern investigator ability."""

import pytest
from backend.cards.guardian.carolyn_fern import CarolynFern
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


def _make_game(with_other=False, other_location="test_location"):
    g = Game("test_carolyn")
    g.chaos_bag.seed(42)

    carolyn_data = make_investigator_data(id="carolyn_fern", name="Carolyn Fern")
    g.register_card_data(carolyn_data)
    loc_data = make_location_data()
    g.register_card_data(loc_data)
    loc_b = make_location_data(id="loc_b", connections=[])
    g.register_card_data(loc_b)
    ally_data = make_asset_data(id="ally_x", cost=2, traits=["ally"], sanity=2)
    g.register_card_data(ally_data)

    g.add_investigator("carolyn", carolyn_data, deck=["filler"] * 10,
                       starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)
    g.add_location("loc_b", loc_b, clues=1)
    if with_other:
        other_data = make_investigator_data(id="other_inv", name="Other")
        g.register_card_data(other_data)
        g.add_investigator("other", other_data, deck=["filler"] * 10,
                           starting_location=other_location)
    return g


def _impl(g):
    return g.card_registry.active_instances["investigator_carolyn"]


def _add_ally(g, instance_id, controller_id, horror=0):
    ally = CardInstance(
        instance_id=instance_id, card_id="ally_x",
        owner_id=controller_id, controller_id=controller_id,
        horror=horror,
    )
    g.state.cards_in_play[instance_id] = ally
    g.state.get_investigator(controller_id).play_area.append(instance_id)
    return ally


class TestSetupActivation:
    def test_setup_activates_impl(self):
        g = _make_game()
        g.setup()
        assert isinstance(_impl(g), CarolynFern)


class TestHealReaction:
    def test_controller_gains_resource_when_ally_healed(self):
        """卡洛琳的效果治愈盟友恐惧后：盟友控制者获得1资源。"""
        g = _make_game(with_other=True)
        g.setup()
        impl = _impl(g)
        other = g.state.get_investigator("other")
        _add_ally(g, "ally_1", "other", horror=1)
        other.resources = 5

        assert impl.notify_horror_healed(
            g.state, "carolyn", target_instance_id="ally_1") is True
        assert other.resources == 6

    def test_healed_investigator_gains_resource(self):
        """治愈调查员恐惧后：该调查员获得1资源。"""
        g = _make_game(with_other=True)
        g.setup()
        impl = _impl(g)
        other = g.state.get_investigator("other")
        other.resources = 5

        assert impl.notify_horror_healed(
            g.state, "carolyn", target_investigator_id="other") is True
        assert other.resources == 6

    def test_no_trigger_for_other_investigators_effect(self):
        """非卡洛琳的卡牌效果治愈：不触发。"""
        g = _make_game(with_other=True)
        g.setup()
        impl = _impl(g)
        other = g.state.get_investigator("other")
        other.resources = 5

        assert impl.notify_horror_healed(
            g.state, "other", target_investigator_id="other") is False
        assert other.resources == 5

    def test_invalid_target_rejected(self):
        """无目标/非盟友实例/未知目标：不触发。"""
        g = _make_game(with_other=True)
        g.setup()
        impl = _impl(g)
        assert impl.notify_horror_healed(g.state, "carolyn") is False
        assert impl.notify_horror_healed(
            g.state, "carolyn", target_instance_id="missing") is False


class TestElderSign:
    def test_elder_sign_heals_investigator_at_location(self):
        """远古印记：+1，治愈所在地点一位调查员的1点恐惧（缺省自己优先按
        玩家顺序）。"""
        g = _make_game()
        g.setup()
        inv = g.state.get_investigator("carolyn")
        inv.horror = 2

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = g.skill_test_engine.run_test(
            investigator_id="carolyn", skill_type=Skill.WILLPOWER, difficulty=99,
        )
        assert result.token_modifier == 1
        assert inv.horror == 1

    def test_elder_sign_heals_ally(self):
        """无调查员有恐惧时：治愈所在地点一张盟友的1点恐惧。"""
        g = _make_game()
        g.setup()
        ally = _add_ally(g, "ally_1", "carolyn", horror=1)

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        g.skill_test_engine.run_test(
            investigator_id="carolyn", skill_type=Skill.WILLPOWER, difficulty=99,
        )
        assert ally.horror == 0

    def test_elder_sign_preset_target(self):
        """预设目标：治愈指定调查员。"""
        g = _make_game(with_other=True)
        g.setup()
        inv = g.state.get_investigator("carolyn")
        other = g.state.get_investigator("other")
        inv.horror = 2
        other.horror = 1
        g.state.scenario.vars["carolyn_fern_elder_target"] = "other"

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        g.skill_test_engine.run_test(
            investigator_id="carolyn", skill_type=Skill.WILLPOWER, difficulty=99,
        )
        assert other.horror == 0
        assert inv.horror == 2  # 未被缺省选中

    def test_elder_sign_ignores_other_locations(self):
        """其他地点的调查员/盟友不在治愈范围。"""
        g = _make_game(with_other=True, other_location="loc_b")
        g.setup()
        other = g.state.get_investigator("other")
        other.horror = 1
        ally = _add_ally(g, "ally_1", "other", horror=1)

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = g.skill_test_engine.run_test(
            investigator_id="carolyn", skill_type=Skill.WILLPOWER, difficulty=99,
        )
        assert result.token_modifier == 1  # +1 仍在
        assert other.horror == 1
        assert ally.horror == 1
