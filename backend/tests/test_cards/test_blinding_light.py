"""Tests for Blinding Light (Level 0)."""

import pytest
from backend.cards.mystic.blinding_light_lv0 import BlindingLight
from backend.engine.event_bus import EventBus
from backend.models.state import GameState, ScenarioState
from backend.tests.conftest import make_event_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    card_data = make_event_data(
        id="blinding_light_lv0", name="Blinding Light",
    )
    state.card_database["blinding_light_lv0"] = card_data

    impl = BlindingLight("inst_bl")
    impl.register(bus, "inst_bl")

    return state, bus, impl


class TestBlindingLight:
    def test_card_id(self, setup):
        state, bus, impl = setup
        assert impl.card_id == "blinding_light_lv0"

    def test_card_data(self, setup):
        state, bus, impl = setup
        card_data = state.card_database["blinding_light_lv0"]
        assert card_data.name == "Blinding Light"
