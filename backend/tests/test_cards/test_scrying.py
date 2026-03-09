"""Tests for Scrying (Level 0)."""

import pytest
from backend.cards.mystic.scrying_lv0 import Scrying
from backend.engine.event_bus import EventBus
from backend.models.state import GameState, ScenarioState
from backend.tests.conftest import make_asset_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    card_data = make_asset_data(
        id="scrying_lv0", name="Scrying",
        traits=["spell"],
    )
    state.card_database["scrying_lv0"] = card_data

    impl = Scrying("inst_scrying")
    impl.register(bus, "inst_scrying")

    return state, bus, impl


class TestScrying:
    def test_card_id(self, setup):
        state, bus, impl = setup
        assert impl.card_id == "scrying_lv0"

    def test_card_data(self, setup):
        state, bus, impl = setup
        card_data = state.card_database["scrying_lv0"]
        assert card_data.name == "Scrying"
