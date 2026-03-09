"""Tests for Medical Texts (Level 0)."""

import pytest
from backend.cards.seeker.medical_texts_lv0 import MedicalTexts
from backend.engine.event_bus import EventBus
from backend.models.state import GameState, InvestigatorState, ScenarioState, CardInstance
from backend.tests.conftest import make_investigator_data, make_asset_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data

    texts_data = make_asset_data(
        id="medical_texts_lv0", name="Medical Texts",
        traits=["tome"],
    )
    state.card_database["medical_texts_lv0"] = texts_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="test_location",
        deck=[],
    )
    state.investigators["inv1"] = inv

    impl = MedicalTexts("inst_texts")
    impl.register(bus, "inst_texts")

    ci = CardInstance(instance_id="inst_texts", card_id="medical_texts_lv0", owner_id="inv1", controller_id="inv1")
    state.cards_in_play["inst_texts"] = ci
    inv.play_area.append("inst_texts")

    return state, bus, inv, impl


class TestMedicalTexts:
    def test_card_data_has_tome_trait(self, setup):
        """Medical Texts has the 'tome' trait."""
        state, bus, inv, impl = setup
        card_data = state.card_database["medical_texts_lv0"]
        assert "tome" in card_data.traits
