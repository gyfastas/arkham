"""Tests for Arcane Studies (Level 0)."""

import pytest
from backend.cards.mystic.arcane_studies_lv0 import ArcaneStudies
from backend.engine.event_bus import EventBus
from backend.models.state import GameState, ScenarioState
from backend.tests.conftest import make_asset_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    card_data = make_asset_data(
        id="arcane_studies_lv0", name="Arcane Studies",
        traits=["talent"],
    )
    state.card_database["arcane_studies_lv0"] = card_data

    impl = ArcaneStudies("inst_as")
    impl.register(bus, "inst_as")

    return state, bus, impl


class TestArcaneStudies:
    def test_card_id(self, setup):
        state, bus, impl = setup
        assert impl.card_id == "arcane_studies_lv0"

    def test_card_data(self, setup):
        state, bus, impl = setup
        card_data = state.card_database["arcane_studies_lv0"]
        assert card_data.name == "Arcane Studies"
