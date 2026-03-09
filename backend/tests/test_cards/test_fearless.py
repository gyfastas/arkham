"""Tests for Fearless (Level 0)."""

import pytest
from backend.cards.mystic.fearless_lv0 import Fearless
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

    inv_data = make_investigator_data(willpower=4)
    state.card_database[inv_data.id] = inv_data

    fearless_data = make_skill_data(
        id="fearless_lv0", skill_icons={"willpower": 1},
    )
    state.card_database["fearless_lv0"] = fearless_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
        deck=["card_a", "card_b"],
    )
    inv.hand.append("fearless_lv0")
    inv.horror = 2
    state.investigators["inv1"] = inv

    impl = Fearless("inst_fearless")
    impl.register(bus, "inst_fearless")

    engine = SkillTestEngine(state, bus, bag)
    return state, bus, bag, engine, inv


class TestFearless:
    def test_card_id(self, setup):
        state, bus, bag, engine, inv = setup
        assert Fearless.card_id == "fearless_lv0"

    def test_heal_horror_on_success(self, setup):
        """Fearless heals 1 horror when committed to a successful test."""
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.PLUS_1]
        initial_horror = inv.horror

        engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.WILLPOWER,
            difficulty=3,
            committed_card_ids=["fearless_lv0"],
        )
        assert inv.horror == initial_horror - 1
