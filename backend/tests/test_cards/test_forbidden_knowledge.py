"""Tests for Forbidden Knowledge (Level 0)."""

import pytest
from backend.cards.mystic.forbidden_knowledge_lv0 import ForbiddenKnowledge
from backend.engine.event_bus import EventBus
from backend.models.state import GameState, ScenarioState
from backend.tests.conftest import make_asset_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    card_data = make_asset_data(
        id="forbidden_knowledge_lv0", name="Forbidden Knowledge",
        traits=["talent"],
    )
    state.card_database["forbidden_knowledge_lv0"] = card_data

    impl = ForbiddenKnowledge("inst_fk")
    impl.register(bus, "inst_fk")

    return state, bus, impl


class TestForbiddenKnowledge:
    def test_card_id(self, setup):
        state, bus, impl = setup
        assert impl.card_id == "forbidden_knowledge_lv0"

    def test_card_data(self, setup):
        state, bus, impl = setup
        card_data = state.card_database["forbidden_knowledge_lv0"]
        assert card_data.name == "Forbidden Knowledge"
