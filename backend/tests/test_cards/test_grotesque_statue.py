"""Tests for Grotesque Statue (Level 4)."""

import pytest
from backend.cards.mystic.grotesque_statue_lv4 import GrotesqueStatue
from backend.engine.event_bus import EventBus
from backend.models.state import GameState, ScenarioState
from backend.tests.conftest import make_asset_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    card_data = make_asset_data(
        id="grotesque_statue_lv4", name="Grotesque Statue",
        traits=["item", "relic"],
    )
    state.card_database["grotesque_statue_lv4"] = card_data

    impl = GrotesqueStatue("inst_gs")
    impl.register(bus, "inst_gs")

    return state, bus, impl


class TestGrotesqueStatue:
    def test_card_id(self, setup):
        state, bus, impl = setup
        assert impl.card_id == "grotesque_statue_lv4"

    def test_card_data(self, setup):
        state, bus, impl = setup
        card_data = state.card_database["grotesque_statue_lv4"]
        assert card_data.name == "Grotesque Statue"
