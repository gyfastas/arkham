"""Tests for Blinding Light (Level 2)."""

import pytest
from backend.cards.mystic.blinding_light_lv2 import BlindingLightLv2
from backend.engine.event_bus import EventBus
from backend.models.state import GameState, ScenarioState
from backend.tests.conftest import make_event_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    card_data = make_event_data(
        id="blinding_light_lv2", name="Blinding Light",
    )
    state.card_database["blinding_light_lv2"] = card_data

    impl = BlindingLightLv2("inst_bl2")
    impl.register(bus, "inst_bl2")

    return state, bus, impl


class TestBlindingLightLv2:
    def test_card_id(self, setup):
        state, bus, impl = setup
        assert impl.card_id == "blinding_light_lv2"

    def test_card_data(self, setup):
        state, bus, impl = setup
        card_data = state.card_database["blinding_light_lv2"]
        assert card_data.name == "Blinding Light"
