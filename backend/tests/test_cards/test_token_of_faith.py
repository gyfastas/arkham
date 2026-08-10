"""Tests for Token of Faith (Level 0)."""

import pytest
from backend.cards.survivor.token_of_faith_lv0 import TokenOfFaith
from backend.engine.event_bus import EventBus
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(combat=3)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv

    inst = CardInstance(
        instance_id="tof_inst", card_id="token_of_faith_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["tof_inst"] = inst
    inv.play_area.append("tof_inst")

    engine = SkillTestEngine(state, bus, bag)
    impl = TokenOfFaith("tof_inst")
    impl.register(bus, "tof_inst")
    impl.bind_chaos_bag(bag)
    return state, bus, bag, engine, inv, inst


class TestTokenOfFaith:
    def test_curse_revealed_adds_bless(self, setup):
        """抽出诅咒标记的检定结束后：消耗本卡，加入1个祝福标记。"""
        state, bus, bag, engine, inv, inst = setup
        bag.tokens = [ChaosTokenType.CURSE]
        before = bag.tokens.count(ChaosTokenType.BLESS)
        engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT, difficulty=5,
        )
        assert inst.exhausted
        assert bag.tokens.count(ChaosTokenType.BLESS) == before + 1

    def test_auto_fail_revealed_adds_bless(self, setup):
        """抽出自动失败标记同样触发。"""
        state, bus, bag, engine, inv, inst = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL]
        before = bag.tokens.count(ChaosTokenType.BLESS)
        engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT, difficulty=3,
        )
        assert inst.exhausted
        assert bag.tokens.count(ChaosTokenType.BLESS) == before + 1

    def test_no_bad_token_no_trigger(self, setup):
        """未抽出诅咒/自动失败：不触发、不消耗。"""
        state, bus, bag, engine, inv, inst = setup
        bag.tokens = [ChaosTokenType.PLUS_1]
        before = bag.tokens.count(ChaosTokenType.BLESS)
        engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT, difficulty=3,
        )
        assert not inst.exhausted
        assert bag.tokens.count(ChaosTokenType.BLESS) == before

    def test_exhausted_token_of_faith_no_trigger(self, setup):
        """本卡已消耗时不统计也不触发。"""
        state, bus, bag, engine, inv, inst = setup
        inst.exhausted = True
        bag.tokens = [ChaosTokenType.CURSE]
        before = bag.tokens.count(ChaosTokenType.BLESS)
        engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT, difficulty=5,
        )
        assert bag.tokens.count(ChaosTokenType.BLESS) == before
