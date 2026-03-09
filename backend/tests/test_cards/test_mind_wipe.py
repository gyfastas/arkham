"""Tests for Mind Wipe (Level 1)."""

import pytest
from backend.cards.mystic.mind_wipe_lv1 import MindWipe
from backend.engine.event_bus import EventBus
from backend.models.state import GameState, ScenarioState
from backend.tests.conftest import make_event_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    card_data = make_event_data(
        id="mind_wipe_lv1", name="Mind Wipe",
    )
    state.card_database["mind_wipe_lv1"] = card_data

    impl = MindWipe("inst_mw")
    impl.register(bus, "inst_mw")

    return state, bus, impl


class TestMindWipe:
    def test_card_id(self, setup):
        state, bus, impl = setup
        assert impl.card_id == "mind_wipe_lv1"

    def test_card_data(self, setup):
        state, bus, impl = setup
        card_data = state.card_database["mind_wipe_lv1"]
        assert card_data.name == "Mind Wipe"
