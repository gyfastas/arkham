"""Tests for Hyperawareness (Level 0)."""

import pytest
from backend.cards.seeker.hyperawareness_lv0 import Hyperawareness
from backend.engine.event_bus import EventBus
from backend.models.state import GameState, InvestigatorState, ScenarioState, CardInstance
from backend.tests.conftest import make_investigator_data, make_asset_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data

    ha_data = make_asset_data(
        id="hyperawareness_lv0", name="Hyperawareness",
        skill_icons={"intellect": 1, "agility": 1},
    )
    state.card_database["hyperawareness_lv0"] = ha_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="test_location",
        deck=[],
    )
    state.investigators["inv1"] = inv

    impl = Hyperawareness("inst_ha")
    impl.register(bus, "inst_ha")

    ci = CardInstance(instance_id="inst_ha", card_id="hyperawareness_lv0", owner_id="inv1", controller_id="inv1")
    state.cards_in_play["inst_ha"] = ci
    inv.play_area.append("inst_ha")

    return state, bus, inv, impl


class TestHyperawareness:
    def test_card_data_icons(self, setup):
        """Hyperawareness has intellect and agility skill icons."""
        state, bus, inv, impl = setup
        card_data = state.card_database["hyperawareness_lv0"]
        assert card_data.skill_icons.get("intellect") == 1
        assert card_data.skill_icons.get("agility") == 1
