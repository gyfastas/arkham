"""Tests for Barricade (Level 0)."""

import pytest
from backend.cards.seeker.barricade_lv0 import Barricade
from backend.engine.event_bus import EventBus
from backend.models.state import GameState, ScenarioState
from backend.tests.conftest import make_event_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    barricade_data = make_event_data(
        id="barricade_lv0", name="Barricade",
    )
    state.card_database["barricade_lv0"] = barricade_data

    impl = Barricade("inst_barricade")
    impl.register(bus, "inst_barricade")

    return state, bus, impl


class TestBarricade:
    def test_card_data(self, setup):
        """Barricade card data is registered correctly."""
        state, bus, impl = setup
        card_data = state.card_database["barricade_lv0"]
        assert card_data.name == "Barricade"
