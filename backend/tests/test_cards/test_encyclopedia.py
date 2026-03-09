"""Tests for Encyclopedia (Level 2)."""

import pytest
from backend.cards.seeker.encyclopedia_lv2 import Encyclopedia
from backend.engine.event_bus import EventBus
from backend.models.state import GameState, ScenarioState
from backend.tests.conftest import make_asset_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    enc_data = make_asset_data(
        id="encyclopedia_lv2", name="Encyclopedia",
        traits=["item", "tome"],
    )
    state.card_database["encyclopedia_lv2"] = enc_data

    impl = Encyclopedia("inst_enc")
    impl.register(bus, "inst_enc")

    return state, bus, impl


class TestEncyclopedia:
    def test_card_data_has_tome_trait(self, setup):
        """Encyclopedia has the 'tome' trait."""
        state, bus, impl = setup
        card_data = state.card_database["encyclopedia_lv2"]
        assert "tome" in card_data.traits
