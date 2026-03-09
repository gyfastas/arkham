"""Tests for Mind over Matter (Level 0)."""

import pytest
from backend.cards.seeker.mind_over_matter_lv0 import MindOverMatter
from backend.engine.event_bus import EventBus
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_investigator_data, make_event_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data

    mom_data = make_event_data(
        id="mind_over_matter_lv0", name="Mind over Matter",
        fast=True,
    )
    state.card_database["mind_over_matter_lv0"] = mom_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="test_location",
        deck=[],
    )
    state.investigators["inv1"] = inv

    impl = MindOverMatter("inst_mom")
    impl.register(bus, "inst_mom")

    return state, bus, inv, impl


class TestMindOverMatter:
    def test_card_data_is_fast(self, setup):
        """Mind over Matter is a fast event."""
        state, bus, inv, impl = setup
        card_data = state.card_database["mind_over_matter_lv0"]
        assert card_data.fast is True
