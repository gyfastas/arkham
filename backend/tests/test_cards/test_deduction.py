"""Tests for Deduction (Level 0)."""

import pytest
from backend.cards.seeker.deduction_lv0 import Deduction
from backend.engine.event_bus import EventBus
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, Skill
from backend.models.state import GameState, InvestigatorState, LocationState, ScenarioState
from backend.tests.conftest import make_investigator_data, make_location_data, make_skill_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(intellect=3)
    state.card_database[inv_data.id] = inv_data

    deduction_data = make_skill_data(id="deduction_lv0", skill_icons={"intellect": 1})
    state.card_database["deduction_lv0"] = deduction_data

    loc_data = make_location_data(shroud=2)
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="test_location",
        deck=["card_a", "card_b"],
    )
    inv.hand.append("deduction_lv0")
    state.investigators["inv1"] = inv

    loc = LocationState(location_id="test_location", card_data=loc_data, clues=3)
    state.locations["test_location"] = loc

    engine = SkillTestEngine(state, bus, bag)

    deduction_impl = Deduction("deduction_impl")
    deduction_impl.register(bus, "deduction_impl")

    return state, bus, bag, engine, inv, loc


class TestDeduction:
    def test_provides_intellect_icon(self, setup):
        state, bus, bag, engine, inv, loc = setup
        bag.tokens = [ChaosTokenType.ZERO]

        result = engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.INTELLECT,
            difficulty=4,
            committed_card_ids=["deduction_lv0"],
        )
        # base 3 + 1 icon + 0 = 4 >= 4
        assert result.success
        assert result.committed_icons == 1

    def test_extra_clue_on_success(self, setup):
        state, bus, bag, engine, inv, loc = setup
        bag.tokens = [ChaosTokenType.PLUS_1]
        initial_clues = inv.clues
        initial_loc_clues = loc.clues

        result = engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.INTELLECT,
            difficulty=2,
            committed_card_ids=["deduction_lv0"],
        )
        assert result.success
        # Deduction grants 1 extra clue (on top of whatever the investigate action gives)
        assert inv.clues == initial_clues + 1
        assert loc.clues == initial_loc_clues - 1

    def test_no_extra_clue_on_failure(self, setup):
        state, bus, bag, engine, inv, loc = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL]
        initial_clues = inv.clues
        initial_loc_clues = loc.clues

        engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.INTELLECT,
            difficulty=2,
            committed_card_ids=["deduction_lv0"],
        )
        assert inv.clues == initial_clues
        assert loc.clues == initial_loc_clues

    def test_no_extra_clue_if_no_clues_left(self, setup):
        state, bus, bag, engine, inv, loc = setup
        bag.tokens = [ChaosTokenType.PLUS_1]
        loc.clues = 0

        engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.INTELLECT,
            difficulty=2,
            committed_card_ids=["deduction_lv0"],
        )
        assert inv.clues == 0
        assert loc.clues == 0

    def test_not_triggered_for_combat(self, setup):
        """Deduction only triggers on intellect tests."""
        state, bus, bag, engine, inv, loc = setup
        bag.tokens = [ChaosTokenType.PLUS_1]
        initial_loc_clues = loc.clues

        engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            difficulty=2,
            committed_card_ids=["deduction_lv0"],
        )
        # No clue gained — wrong skill type
        assert loc.clues == initial_loc_clues
