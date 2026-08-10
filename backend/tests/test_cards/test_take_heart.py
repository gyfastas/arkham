"""Tests for Take Heart (Level 0)."""

import pytest
from backend.cards.survivor.take_heart_lv0 import TakeHeart
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

    inv_data = make_investigator_data(willpower=3)
    state.card_database[inv_data.id] = inv_data
    state.card_database["take_heart_lv0"] = make_skill_data(
        id="take_heart_lv0", skill_icons={})

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        hand=["take_heart_lv0"], deck=["card_a", "card_b", "card_c"],
        resources=1,
    )
    state.investigators["inv1"] = inv

    engine = SkillTestEngine(state, bus, bag)
    impl = TakeHeart("th_inst")
    impl.register(bus, "th_inst")
    return state, bus, bag, engine, inv


class TestTakeHeart:
    def test_failed_test_draws_2_and_gains_2(self, setup):
        """检定失败：抽2张牌、获得2资源。"""
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL]
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.WILLPOWER,
            difficulty=4, committed_card_ids=["take_heart_lv0"],
        )
        assert not result.success
        assert "card_a" in inv.hand and "card_b" in inv.hand
        assert inv.deck == ["card_c"]
        assert inv.resources == 3

    def test_successful_test_no_effect(self, setup):
        """检定成功：无效果。"""
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.PLUS_1]
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.WILLPOWER,
            difficulty=4, committed_card_ids=["take_heart_lv0"],
        )
        assert result.success
        assert inv.hand == ["take_heart_lv0"] or "card_a" not in inv.hand
        assert inv.resources == 1

    def test_deck_smaller_than_2(self, setup):
        """牌堆不足2张：抽尽即可，资源照常+2。"""
        state, bus, bag, engine, inv = setup
        inv.deck = ["only_card"]
        bag.tokens = [ChaosTokenType.AUTO_FAIL]
        engine.run_test(
            investigator_id="inv1", skill_type=Skill.WILLPOWER,
            difficulty=4, committed_card_ids=["take_heart_lv0"],
        )
        assert "only_card" in inv.hand
        assert inv.deck == []
        assert inv.resources == 3
