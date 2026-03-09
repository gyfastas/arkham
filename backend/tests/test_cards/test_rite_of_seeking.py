"""Tests for Rite of Seeking (Level 2)."""

import pytest
from backend.cards.mystic.rite_of_seeking_lv2 import RiteOfSeeking
from backend.engine.event_bus import EventBus
from backend.models.state import GameState, ScenarioState
from backend.tests.conftest import make_asset_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    card_data = make_asset_data(
        id="rite_of_seeking_lv2", name="Rite of Seeking",
        traits=["spell"],
    )
    state.card_database["rite_of_seeking_lv2"] = card_data

    impl = RiteOfSeeking("inst_ros")
    impl.register(bus, "inst_ros")

    return state, bus, impl


class TestRiteOfSeeking:
    def test_card_id(self, setup):
        state, bus, impl = setup
        assert impl.card_id == "rite_of_seeking_lv2"

    def test_card_data(self, setup):
        state, bus, impl = setup
        card_data = state.card_database["rite_of_seeking_lv2"]
        assert card_data.name == "Rite of Seeking"
