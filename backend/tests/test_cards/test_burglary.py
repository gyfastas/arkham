"""Tests for Burglary (Level 0)."""

import pytest
from backend.cards.rogue.burglary_lv0 import Burglary
from backend.engine.event_bus import EventBus
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_investigator_data, make_asset_data


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

    impl = Burglary("burglary_inst")
    impl.register(bus, "burglary_inst")
    return state, bus, inv, impl


class TestBurglary:
    def test_card_id(self, setup):
        """Burglary has correct card_id."""
        assert Burglary.card_id == "burglary_lv0"

    def test_class_exists(self, setup):
        """Implementation class is instantiable."""
        state, bus, inv, impl = setup
        assert impl.instance_id == "burglary_inst"
