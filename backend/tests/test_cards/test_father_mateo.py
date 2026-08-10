"""Tests for Father Mateo investigator ability."""

import pytest
from backend.cards.mystic.father_mateo import FatherMateo
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.tests.conftest import (
    make_investigator_data, make_location_data,
)


def _make_game(with_mateo=True, with_other=False):
    g = Game("test_mateo")
    g.chaos_bag.seed(42)

    loc_data = make_location_data()
    g.register_card_data(loc_data)
    g.add_location("test_location", loc_data, clues=3)

    if with_mateo:
        mateo_data = make_investigator_data(id="father_mateo",
                                            name="Father Mateo", willpower=4)
        g.register_card_data(mateo_data)
        g.add_investigator("mateo", mateo_data, deck=["filler"] * 10,
                           starting_location="test_location")
    if with_other:
        other_data = make_investigator_data(id="other_inv", name="Other",
                                            intellect=3)
        g.register_card_data(other_data)
        g.add_investigator("other", other_data, deck=["filler"] * 10,
                           starting_location="test_location")
    return g


def _impl(g):
    return g.card_registry.active_instances["investigator_mateo"]


class TestSetupActivation:
    def test_setup_activates_impl(self):
        g = _make_game()
        g.setup()
        assert isinstance(_impl(g), FatherMateo)


class TestCancelAutoFail:
    def test_cancel_other_investigators_auto_fail(self):
        """其他调查员抽出自动失败：取消并视为远古印记（每场限1次）。"""
        g = _make_game(with_other=True)
        g.setup()

        g.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]
        result = g.skill_test_engine.run_test(
            investigator_id="other", skill_type=Skill.INTELLECT, difficulty=2,
        )
        assert result.auto_fail is False  # 被取消
        assert result.token == ChaosTokenType.AUTO_FAIL  # 揭示记录不变
        assert result.token_modifier == 0  # 视为远古印记：无数值修正
        assert result.success is True  # 智力3 vs 难度2

        # 每场游戏限1次：第二个自动失败照常结算
        result2 = g.skill_test_engine.run_test(
            investigator_id="other", skill_type=Skill.INTELLECT, difficulty=2,
        )
        assert result2.auto_fail is True
        assert result2.success is False

    def test_no_cancel_without_mateo_in_game(self):
        """马泰奥不在游戏中时不取消。"""
        g = _make_game(with_mateo=False, with_other=True)
        g.setup()
        # 手工注册马泰奥实现（本人不在场）
        impl = FatherMateo("test_instance")
        impl.register(g.event_bus, "test_instance")

        g.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]
        result = g.skill_test_engine.run_test(
            investigator_id="other", skill_type=Skill.INTELLECT, difficulty=2,
        )
        assert result.auto_fail is True
        assert result.success is False

    def test_mateo_own_auto_fail_converts_and_auto_succeeds(self):
        """马泰奥自己抽出自动失败：转为远古印记并触发其效果（自动成功）。"""
        g = _make_game()
        g.setup()
        inv = g.state.get_investigator("mateo")
        hand_before = len(inv.hand)
        resources_before = inv.resources

        g.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]
        result = g.skill_test_engine.run_test(
            investigator_id="mateo", skill_type=Skill.WILLPOWER, difficulty=99,
        )
        assert result.auto_fail is False
        assert result.success is True  # 远古印记：自动成功
        # 检定结束后缺省选择：抽1牌+1资源
        assert len(inv.hand) == hand_before + 1
        assert inv.resources == resources_before + 1


class TestElderSign:
    def test_auto_success_on_impossible_difficulty(self):
        """远古印记：自动成功（远超难度的检定也成功）。"""
        g = _make_game()
        g.setup()

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = g.skill_test_engine.run_test(
            investigator_id="mateo", skill_type=Skill.WILLPOWER, difficulty=99,
        )
        assert result.success is True
        assert result.token_modifier == 0  # 印记本身无数值加值

    def test_post_test_extra_action_on_his_turn(self):
        """检定结束后选择额外行动（须为他的回合）。"""
        g = _make_game()
        g.setup()
        inv = g.state.get_investigator("mateo")
        g.state.scenario.vars["father_mateo_elder_choice"] = "action"

        g.event_bus.emit(EventContext(
            game_state=g.state,
            event=GameEvent.INVESTIGATOR_TURN_BEGINS,
            investigator_id="mateo",
        ))
        inv.actions_remaining = 3
        hand_before = len(inv.hand)
        resources_before = inv.resources

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        g.skill_test_engine.run_test(
            investigator_id="mateo", skill_type=Skill.WILLPOWER, difficulty=1,
        )
        assert inv.actions_remaining == 4
        assert len(inv.hand) == hand_before  # 未走抽牌分支
        assert inv.resources == resources_before

    def test_action_choice_falls_back_when_not_his_turn(self):
        """预设额外行动但不是他的回合：回退为抽1牌+1资源。"""
        g = _make_game()
        g.setup()
        inv = g.state.get_investigator("mateo")
        g.state.scenario.vars["father_mateo_elder_choice"] = "action"
        inv.actions_remaining = 3
        hand_before = len(inv.hand)

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        g.skill_test_engine.run_test(
            investigator_id="mateo", skill_type=Skill.WILLPOWER, difficulty=1,
        )
        assert inv.actions_remaining == 3
        assert len(inv.hand) == hand_before + 1
