"""Tests for Strength in Numbers (Level 1)."""

import pytest
from backend.cards.survivor.strength_in_numbers_lv1 import StrengthInNumbers
from backend.engine.event_bus import EventBus
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, PlayerClass, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_skill_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    # 调查员：中立（区别于幸存者，便于计数）
    inv_data = make_investigator_data(combat=3)
    state.card_database[inv_data.id] = inv_data
    state.card_database["strength_in_numbers_lv1"] = make_skill_data(
        id="strength_in_numbers_lv1", skill_icons={"wild": 1},
        card_class=PlayerClass.SURVIVOR)
    state.card_database["survivor_asset"] = make_asset_data(
        id="survivor_asset", card_class=PlayerClass.SURVIVOR)
    state.card_database["guardian_asset"] = make_asset_data(
        id="guardian_asset", card_class=PlayerClass.GUARDIAN)

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data,
        location_id="loc1", hand=["strength_in_numbers_lv1"],
    )
    state.investigators["inv1"] = inv

    engine = SkillTestEngine(state, bus, bag)
    impl = StrengthInNumbers("sin_inst")
    impl.register(bus, "sin_inst")
    return state, bus, bag, engine, inv


def _add_asset(state, inv, instance_id, card_id):
    state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="inv1", controller_id="inv1",
    )
    inv.play_area.append(instance_id)


class TestStrengthInNumbers:
    def test_one_icon_per_different_class(self, setup):
        """调查员(neutral)+场上survivor资产+本卡(survivor)=2职阶 → +2图标。"""
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.ZERO]
        _add_asset(state, inv, "a1", "survivor_asset")
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT,
            difficulty=6, committed_card_ids=["strength_in_numbers_lv1"],
        )
        # 印刷1万能 + 2职阶 = 3图标；base 3 + 3 + 0 = 6
        assert result.committed_icons == 3
        assert result.success

    def test_two_in_play_classes(self, setup):
        """场上含 survivor+guardian：neutral+survivor+guardian=3职阶 → +3图标。"""
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.ZERO]
        _add_asset(state, inv, "a1", "survivor_asset")
        _add_asset(state, inv, "a2", "guardian_asset")
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT,
            difficulty=7, committed_card_ids=["strength_in_numbers_lv1"],
        )
        assert result.committed_icons == 4  # 印刷1 + 3职阶
        assert result.success

    def test_alone_counts_investigator_and_self(self, setup):
        """无场上卡：调查员(neutral)+本卡(survivor)=2职阶 → +2图标。"""
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.ZERO]
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT,
            difficulty=6, committed_card_ids=["strength_in_numbers_lv1"],
        )
        assert result.committed_icons == 3
        assert result.success

    def test_no_effect_when_not_committed(self, setup):
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.ZERO]
        result = engine.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT, difficulty=4,
        )
        assert result.committed_icons == 0
        assert not result.success
