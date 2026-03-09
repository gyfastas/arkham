"""Tests for Scrying (Level 3)."""

import pytest
from backend.cards.mystic.scrying_lv3 import ScryingLv3
from backend.engine.event_bus import EventBus
from backend.models.state import GameState, ScenarioState
from backend.tests.conftest import make_asset_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    card_data = make_asset_data(
        id="scrying_lv3", name="Scrying",
        traits=["spell"],
    )
    state.card_database["scrying_lv3"] = card_data

    impl = ScryingLv3("inst_scrying3")
    impl.register(bus, "inst_scrying3")

    return state, bus, impl


class TestScryingLv3:
    def test_card_id(self, setup):
        state, bus, impl = setup
        assert impl.card_id == "scrying_lv3"

    def test_card_data(self, setup):
        state, bus, impl = setup
        card_data = state.card_database["scrying_lv3"]
        assert card_data.name == "Scrying"
