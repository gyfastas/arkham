"""Tests for Knife (Level 0)."""

import pytest
from backend.cards.neutral.knife_lv0 import Knife
from backend.engine.event_bus import EventBus
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, PlayerClass, Skill, SlotType
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_investigator_data, make_asset_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(combat=3)
    state.card_database[inv_data.id] = inv_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
        deck=["card_a", "card_b"],
    )
    inv.play_area.append("knife_inst")
    state.investigators["inv1"] = inv

    engine = SkillTestEngine(state, bus, bag)

    impl = Knife("knife_inst")
    impl.register(bus, "knife_inst")

    return state, bus, bag, engine, inv


class TestKnife:
    def test_combat_bonus(self, setup):
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.ZERO]

        result = engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            difficulty=4,
        )
        # base 3 + 1 knife bonus + 0 = 4 >= 4
        assert result.success

    def test_no_bonus_on_intellect(self, setup):
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.ZERO]

        result = engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.INTELLECT,
            difficulty=4,
        )
        # base 3 + 0 (no knife bonus for intellect) = 3 < 4
        assert not result.success
