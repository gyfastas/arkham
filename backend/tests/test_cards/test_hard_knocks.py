"""Tests for Hard Knocks (Level 0)."""

import pytest
from backend.cards.rogue.hard_knocks_lv0 import HardKnocks
from backend.engine.event_bus import EventBus
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
    )
    state.investigators["inv1"] = inv

    impl = HardKnocks("hk_inst")
    impl.register(bus, "hk_inst")
    return state, bus, inv, impl


class TestHardKnocks:
    def test_card_id(self, setup):
        """Hard Knocks has correct card_id."""
        assert HardKnocks.card_id == "hard_knocks_lv0"

    def test_class_exists(self, setup):
        """Implementation class is instantiable."""
        state, bus, inv, impl = setup
        assert impl.instance_id == "hk_inst"
