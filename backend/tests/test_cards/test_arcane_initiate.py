"""Tests for Arcane Initiate (Level 0)."""

import pytest
from backend.cards.mystic.arcane_initiate_lv0 import ArcaneInitiate
from backend.engine.event_bus import EventBus
from backend.models.state import GameState, ScenarioState
from backend.tests.conftest import make_asset_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    card_data = make_asset_data(
        id="arcane_initiate_lv0", name="Arcane Initiate",
        traits=["ally", "sorcerer"],
    )
    state.card_database["arcane_initiate_lv0"] = card_data

    impl = ArcaneInitiate("inst_ai")
    impl.register(bus, "inst_ai")

    return state, bus, impl


class TestArcaneInitiate:
    def test_card_id(self, setup):
        state, bus, impl = setup
        assert impl.card_id == "arcane_initiate_lv0"

    def test_card_data(self, setup):
        state, bus, impl = setup
        card_data = state.card_database["arcane_initiate_lv0"]
        assert card_data.name == "Arcane Initiate"
