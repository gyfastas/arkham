"""Tests for Third Time's a Charm (Level 2)."""

import pytest
from backend.cards.survivor.third_times_a_charm_lv2 import ThirdTimesACharm
from backend.engine.event_bus import EventBus
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, Skill
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_event_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(combat=3)
    state.card_database[inv_data.id] = inv_data
    state.card_database["third_times_a_charm_lv2"] = make_event_data(
        id="third_times_a_charm_lv2", cost=1, fast=True)

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        hand=["third_times_a_charm_lv2"], resources=3,
    )
    state.investigators["inv1"] = inv

    engine = SkillTestEngine(state, bus, bag)
    impl = ThirdTimesACharm("ttac_inst")
    impl.register(bus, "ttac_inst")
    impl.bind_chaos_bag(bag)
    return state, bus, bag, engine, inv, impl


def _script_draws(bag, tokens):
    """让袋的 draw() 按脚本返回（取消重抽消耗同一只袋）。"""
    draws = iter(tokens)
    bag.draw = lambda: next(draws)


class TestThirdTimesACharm:
    def test_auto_play_and_reroll_negative_token(self, setup):
        """检定开始自动打出；负修正标记被取消并重抽。"""
        state, bus, bag, engine, inv, impl = setup
        bag.tokens = [ChaosTokenType.MINUS_3, ChaosTokenType.PLUS_1]
        _script_draws(bag, [ChaosTokenType.MINUS_3, ChaosTokenType.PLUS_1])

        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT, difficulty=4,
        )
        # 自动打出：付费、入弃牌堆
        assert inv.resources == 2
        assert "third_times_a_charm_lv2" in inv.discard
        # 标记由 -3 重抽为 +1：3 + 1 = 4 >= 4
        assert result.token_modifier == 1
        assert result.success
        # 用掉1次取消重抽（日志记录"剩1次"）
        assert any("重抽为 +1" in m and "剩1次" in m for m in state.effect_log)

    def test_reroll_auto_fail_token(self, setup):
        """自动失败标记被取消重抽（cancel_auto_fail 通道）。"""
        state, bus, bag, engine, inv, impl = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL, ChaosTokenType.ZERO]
        _script_draws(bag, [ChaosTokenType.AUTO_FAIL, ChaosTokenType.ZERO])

        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT, difficulty=3,
        )
        assert not result.auto_fail
        assert result.success

    def test_reroll_limited_to_two(self, setup):
        """每次检定最多取消重抽2次。"""
        state, bus, bag, engine, inv, impl = setup
        bag.tokens = [ChaosTokenType.MINUS_1]
        _script_draws(bag, [ChaosTokenType.MINUS_1] * 5)

        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT, difficulty=3,
        )
        # 重抽2次后仍是 -1：3 - 1 = 2 < 3 失败
        assert result.token_modifier == -1
        assert not result.success
        # 每次检定最多取消重抽2次
        rerolls = [m for m in state.effect_log if "事不过三：取消" in m]
        assert len(rerolls) == 2

    def test_good_token_kept(self, setup):
        """非负标记不触发取消。"""
        state, bus, bag, engine, inv, impl = setup
        bag.tokens = [ChaosTokenType.PLUS_1]
        _script_draws(bag, [ChaosTokenType.PLUS_1])

        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT, difficulty=4,
        )
        assert result.token_modifier == 1
        assert result.success
        assert not any("事不过三：取消" in m for m in state.effect_log)

    def test_no_auto_play_without_resources(self, setup):
        """资源不足时不自动打出。"""
        state, bus, bag, engine, inv, impl = setup
        inv.resources = 0
        bag.tokens = [ChaosTokenType.MINUS_3]
        _script_draws(bag, [ChaosTokenType.MINUS_3])

        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT, difficulty=4,
        )
        assert "third_times_a_charm_lv2" in inv.hand
        assert result.token_modifier == -3
        assert not result.success
