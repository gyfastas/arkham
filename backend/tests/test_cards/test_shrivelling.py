"""Tests for Shrivelling (Level 0)."""

import pytest
from backend.cards.mystic.shrivelling_lv0 import Shrivelling
from backend.engine.event_bus import EventBus
from backend.models.state import GameState, ScenarioState
from backend.tests.conftest import make_asset_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    card_data = make_asset_data(
        id="shrivelling_lv0", name="Shrivelling",
        traits=["spell"],
    )
    state.card_database["shrivelling_lv0"] = card_data

    impl = Shrivelling("inst_shriv")
    impl.register(bus, "inst_shriv")

    return state, bus, impl


class TestShrivelling:
    def test_card_id(self, setup):
        state, bus, impl = setup
        assert impl.card_id == "shrivelling_lv0"

    def test_card_data(self, setup):
        state, bus, impl = setup
        card_data = state.card_database["shrivelling_lv0"]
        assert card_data.name == "Shrivelling"
