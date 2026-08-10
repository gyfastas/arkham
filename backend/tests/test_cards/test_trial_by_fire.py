"""Tests for Trial by Fire (Level 0)."""

import pytest
from backend.cards.survivor.trial_by_fire_lv0 import TrialByFire
from backend.engine.event_bus import EventBus, EventContext
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_event_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(willpower=2, intellect=3, combat=3, agility=4)
    state.card_database[inv_data.id] = inv_data
    state.card_database["trial_by_fire_lv0"] = make_event_data(
        id="trial_by_fire_lv0", cost=3, fast=True)

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv

    engine = SkillTestEngine(state, bus, bag)
    impl = TrialByFire("tbf_inst")
    impl.register(bus, "tbf_inst")
    return state, bus, bag, engine, inv, impl


def _play(bus, state, **extra):
    ctx = EventContext(
        game_state=state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "trial_by_fire_lv0", **extra},
    )
    bus.emit(ctx)
    return ctx


class TestTrialByFire:
    def test_chosen_skill_set_to_5(self, setup):
        """指定战斗：基础值设为5（3→5，+2修正）。"""
        state, bus, bag, engine, inv, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]
        ctx = _play(bus, state, skill="combat")
        assert ctx.extra["trial_by_fire_skill"] == "combat"
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT, difficulty=5,
        )
        assert result.modified_skill == 5
        assert result.success

    def test_auto_picks_lowest_skill(self, setup):
        """未指定时自动选基础值最低的技能（意志2）。"""
        state, bus, bag, engine, inv, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]
        ctx = _play(bus, state)
        assert ctx.extra["trial_by_fire_skill"] == "willpower"
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.WILLPOWER, difficulty=5,
        )
        assert result.modified_skill == 5
        assert result.success

    def test_other_skills_unaffected(self, setup):
        """未选择的技能不受影响。"""
        state, bus, bag, engine, inv, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]
        _play(bus, state, skill="combat")
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.INTELLECT, difficulty=4,
        )
        assert result.modified_skill == 3  # 智力3+0，未设为5
        assert not result.success

    def test_expires_at_turn_end(self, setup):
        """回合结束后效果失效。"""
        state, bus, bag, engine, inv, impl = setup
        bag.tokens = [ChaosTokenType.ZERO, ChaosTokenType.ZERO]
        _play(bus, state, skill="combat")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="inv1",
        ))
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT, difficulty=5,
        )
        assert result.modified_skill == 3
        assert not result.success

    def test_lowers_high_base_skill(self, setup):
        """基础值高于5时同样设为5（官方"设为"语义）：敏捷4→5反而+1。"""
        state, bus, bag, engine, inv, impl = setup
        inv.card_data.skills.agility = 6
        bag.tokens = [ChaosTokenType.ZERO]
        _play(bus, state, skill="agility")
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.AGILITY, difficulty=5,
        )
        assert result.modified_skill == 5
        assert result.success
