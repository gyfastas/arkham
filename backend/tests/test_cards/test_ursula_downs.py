"""Tests for Ursula Downs investigator ability."""

import pytest
from backend.cards.seeker.ursula_downs import UrsulaDowns
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, GameEvent, Skill
from backend.tests.conftest import (
    make_investigator_data, make_location_data,
)


def _make_game():
    g = Game("test_ursula")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="ursula_downs", name="Ursula Downs",
                                      intellect=4)
    g.register_card_data(inv_data)
    loc_a = make_location_data(id="loc_a", shroud=2, clue_value=2,
                               connections=["loc_b"])
    loc_b = make_location_data(id="loc_b", shroud=2, clue_value=1,
                               connections=["loc_a"])
    g.register_card_data(loc_a)
    g.register_card_data(loc_b)

    g.add_investigator("ursula", inv_data, deck=["filler"] * 10,
                       starting_location="loc_a")
    g.add_location("loc_a", loc_a, clues=2)
    g.add_location("loc_b", loc_b, clues=1)
    return g


def _impl(g):
    return g.card_registry.active_instances["investigator_ursula"]


def _move(g, destination):
    assert g.action_resolver.perform_action("ursula", Action.MOVE,
                                            destination=destination)


class TestSetupActivation:
    def test_setup_activates_impl(self):
        g = _make_game()
        g.setup()
        assert isinstance(_impl(g), UrsulaDowns)


class TestFreeInvestigateAfterMove:
    def test_move_arms_free_investigate(self):
        """移动后可进行一次免费调查：成功发现线索，不扣行动。"""
        g = _make_game()
        g.setup()
        impl = _impl(g)
        inv = g.state.get_investigator("ursula")
        inv.actions_remaining = 3

        _move(g, "loc_b")
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        assert impl.activate_free_investigate(g, "ursula") is True

        assert inv.clues == 1
        assert g.state.locations["loc_b"].clues == 0
        assert inv.actions_remaining == 2  # 移动扣1，免费调查不扣

    def test_limit_once_per_round(self):
        """每轮限1次：第二次移动不再武装；新一轮重置。"""
        g = _make_game()
        g.setup()
        impl = _impl(g)
        inv = g.state.get_investigator("ursula")
        inv.actions_remaining = 3

        _move(g, "loc_b")
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        assert impl.activate_free_investigate(g, "ursula") is True

        # 同轮第二次移动：不再武装
        _move(g, "loc_a")
        assert impl.activate_free_investigate(g, "ursula") is False

        # 新一轮：重置
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.ROUND_BEGINS,
        ))
        _move(g, "loc_b")
        assert impl.activate_free_investigate(g, "ursula") is True

    def test_no_investigate_without_move(self):
        """未移动时不可发动免费调查。"""
        g = _make_game()
        g.setup()
        impl = _impl(g)
        assert impl.activate_free_investigate(g, "ursula") is False


class TestElderSignMove:
    def test_elder_sign_arms_post_test_move(self):
        """远古印记：+1，检定结束后可移动到一个连接地点。"""
        g = _make_game()
        g.setup()
        impl = _impl(g)
        inv = g.state.get_investigator("ursula")

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = g.skill_test_engine.run_test(
            investigator_id="ursula", skill_type=Skill.AGILITY, difficulty=1,
        )
        assert result.token_modifier == 1

        assert impl.activate_elder_move(g.state, "ursula", "loc_b") is True
        assert inv.location_id == "loc_b"
        # 窗口一次性
        assert impl.activate_elder_move(g.state, "ursula", "loc_a") is False

    def test_elder_move_requires_connection(self):
        """只能移动到连接地点。"""
        g = _make_game()
        g.setup()
        impl = _impl(g)
        inv = g.state.get_investigator("ursula")

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        g.skill_test_engine.run_test(
            investigator_id="ursula", skill_type=Skill.AGILITY, difficulty=1,
        )
        assert impl.activate_elder_move(g.state, "ursula", "loc_c") is False
        assert inv.location_id == "loc_a"
        # 窗口仍开着：合法目标可用
        assert impl.activate_elder_move(g.state, "ursula", "loc_b") is True

    def test_elder_move_expires_at_next_test(self):
        """移动窗口在下一次检定开始时关闭。"""
        g = _make_game()
        g.setup()
        impl = _impl(g)

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        g.skill_test_engine.run_test(
            investigator_id="ursula", skill_type=Skill.AGILITY, difficulty=1,
        )
        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        g.skill_test_engine.run_test(
            investigator_id="ursula", skill_type=Skill.AGILITY, difficulty=1,
        )
        assert impl.activate_elder_move(g.state, "ursula", "loc_b") is False
