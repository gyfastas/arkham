"""Tests for Overpower (Level 0)."""

import pytest
from backend.cards.neutral.overpower_lv0 import Overpower
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

    op_data = make_skill_data(id="overpower_lv0", skill_icons={"combat": 2})
    state.card_database["overpower_lv0"] = op_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
        deck=["card_a", "card_b", "card_c"],
    )
    inv.hand.append("overpower_lv0")
    state.investigators["inv1"] = inv

    engine = SkillTestEngine(state, bus, bag)

    impl = Overpower("op_impl")
    impl.register(bus, "op_impl")

    return state, bus, bag, engine, inv


class TestOverpower:
    def test_draw_card_on_success(self, setup):
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.ZERO]
        initial_deck = len(inv.deck)

        result = engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            difficulty=3,
            committed_card_ids=["overpower_lv0"],
        )
        assert result.success
        assert len(inv.deck) == initial_deck - 1

    def test_no_draw_on_failure(self, setup):
        state, bus, bag, engine, inv = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL]
        initial_deck = len(inv.deck)

        engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            difficulty=3,
            committed_card_ids=["overpower_lv0"],
        )
        assert len(inv.deck) == initial_deck
