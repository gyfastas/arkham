"""Tests for Signum Crucis (Level 2)."""

import pytest
from backend.cards.survivor.signum_crucis_lv2 import SignumCrucis
from backend.engine.event_bus import EventBus
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, Skill
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_investigator_data, make_skill_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(combat=3)
    state.card_database[inv_data.id] = inv_data
    state.card_database["signum_crucis_lv2"] = make_skill_data(
        id="signum_crucis_lv2", skill_icons={"wild": 1})

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data,
        location_id="loc1", hand=["signum_crucis_lv2"],
    )
    state.investigators["inv1"] = inv

    engine = SkillTestEngine(state, bus, bag)
    impl = SignumCrucis("sc_inst")
    impl.register(bus, "sc_inst")
    impl.bind_chaos_bag(bag)
    return state, bus, bag, engine, inv


class TestSignumCrucis:
    def test_adds_bless_equal_to_difference(self, setup):
        """难度5 vs 基础3：加入2个祝福标记。"""
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.ZERO]
        before = bag.tokens.count(ChaosTokenType.BLESS)
        engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT,
            difficulty=5, committed_card_ids=["signum_crucis_lv2"],
        )
        assert bag.tokens.count(ChaosTokenType.BLESS) == before + 2

    def test_no_bless_when_difficulty_not_higher(self, setup):
        """难度不高于基础技能值：不加标记。"""
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.ZERO]
        before = bag.tokens.count(ChaosTokenType.BLESS)
        engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT,
            difficulty=3, committed_card_ids=["signum_crucis_lv2"],
        )
        assert bag.tokens.count(ChaosTokenType.BLESS) == before

    def test_not_committed_no_effect(self, setup):
        """未投入本卡：不加标记。"""
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.ZERO]
        before = bag.tokens.count(ChaosTokenType.BLESS)
        engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT, difficulty=6,
        )
        assert bag.tokens.count(ChaosTokenType.BLESS) == before
