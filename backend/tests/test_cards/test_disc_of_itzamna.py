"""Tests for Disc of Itzamna (Level 2)."""

import pytest
from backend.cards.seeker.disc_of_itzamna_lv2 import DiscOfItzamna
from backend.engine.event_bus import EventBus
from backend.models.state import GameState, ScenarioState
from backend.tests.conftest import make_asset_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    disc_data = make_asset_data(
        id="disc_of_itzamna_lv2", name="Disc of Itzamna",
        traits=["item", "relic"],
    )
    state.card_database["disc_of_itzamna_lv2"] = disc_data

    impl = DiscOfItzamna("inst_disc")
    impl.register(bus, "inst_disc")

    return state, bus, impl


class TestDiscOfItzamna:
    def test_card_data_has_relic_trait(self, setup):
        """Disc of Itzamna has the 'relic' trait."""
        state, bus, impl = setup
        card_data = state.card_database["disc_of_itzamna_lv2"]
        assert "relic" in card_data.traits
