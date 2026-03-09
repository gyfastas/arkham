"""Tests for Dr. Milan Christopher (Level 0)."""

import pytest
from backend.cards.seeker.dr_milan_christopher_lv0 import DrMilanChristopher
from backend.engine.event_bus import EventBus
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, Skill
from backend.models.state import GameState, InvestigatorState, LocationState, ScenarioState, CardInstance
from backend.tests.conftest import make_investigator_data, make_location_data, make_asset_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(intellect=3)
    state.card_database[inv_data.id] = inv_data

    milan_data = make_asset_data(
        id="dr_milan_christopher_lv0", name="Dr. Milan Christopher",
        traits=["ally", "miskatonic"],
    )
    state.card_database["dr_milan_christopher_lv0"] = milan_data

    loc_data = make_location_data(shroud=3)
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="test_location",
        deck=["card_a", "card_b"],
    )
    state.investigators["inv1"] = inv

    loc = LocationState(location_id="test_location", card_data=loc_data, clues=3)
    state.locations["test_location"] = loc

    impl = DrMilanChristopher("inst_milan")
    impl.register(bus, "inst_milan")

    ci = CardInstance(instance_id="inst_milan", card_id="dr_milan_christopher_lv0", owner_id="inv1", controller_id="inv1")
    state.cards_in_play["inst_milan"] = ci
    inv.play_area.append("inst_milan")

    engine = SkillTestEngine(state, bus, bag)
    return state, bus, bag, engine, inv, loc


class TestDrMilanChristopher:
    def test_intellect_bonus(self, setup):
        """Dr. Milan provides +1 intellect during skill tests."""
        state, bus, bag, engine, inv, loc = setup
        bag.tokens = [ChaosTokenType.ZERO]

        # Base intellect 3 + 1 Milan bonus = 4 vs difficulty 4 -> success
        result = engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.INTELLECT,
            difficulty=4,
        )
        assert result.success

    def test_resource_on_investigate_success(self, setup):
        """After a successful intellect test, gain 1 resource."""
        state, bus, bag, engine, inv, loc = setup
        bag.tokens = [ChaosTokenType.PLUS_1]
        initial_resources = inv.resources

        engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.INTELLECT,
            difficulty=2,
        )
        assert inv.resources == initial_resources + 1

    def test_no_resource_on_failure(self, setup):
        """No resource gained when the intellect test fails."""
        state, bus, bag, engine, inv, loc = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL]
        initial_resources = inv.resources

        engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.INTELLECT,
            difficulty=2,
        )
        assert inv.resources == initial_resources
