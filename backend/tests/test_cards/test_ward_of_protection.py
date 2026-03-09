"""Tests for Ward of Protection (Level 0)."""

import pytest
from backend.cards.mystic.ward_of_protection_lv0 import WardOfProtection
from backend.engine.event_bus import EventBus
from backend.models.state import GameState, ScenarioState
from backend.tests.conftest import make_event_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    card_data = make_event_data(
        id="ward_of_protection_lv0", name="Ward of Protection",
    )
    state.card_database["ward_of_protection_lv0"] = card_data

    impl = WardOfProtection("inst_wop")
    impl.register(bus, "inst_wop")

    return state, bus, impl


class TestWardOfProtection:
    def test_card_id(self, setup):
        state, bus, impl = setup
        assert impl.card_id == "ward_of_protection_lv0"

    def test_card_data(self, setup):
        state, bus, impl = setup
        card_data = state.card_database["ward_of_protection_lv0"]
        assert card_data.name == "Ward of Protection"
