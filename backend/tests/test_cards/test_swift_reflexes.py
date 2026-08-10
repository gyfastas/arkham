"""Tests for Swift Reflexes (Level 0)."""

import pytest

from backend.cards.rogue.swift_reflexes_lv0 import SwiftReflexes
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    inv.actions_remaining = 2
    state.investigators["inv1"] = inv
    impl = SwiftReflexes("sr_inst")
    impl.register(bus, "sr_inst")
    return state, bus, inv


class TestSwiftReflexes:
    def test_grants_extra_action(self, setup):
        state, bus, inv = setup
        ctx = EventContext(
            game_state=state,
            event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "swift_reflexes_lv0"},
        )
        bus.emit(ctx)
        assert inv.actions_remaining == 3
        assert ctx.extra["swift_reflexes_action"] is True

    def test_other_card_ignored(self, setup):
        state, bus, inv = setup
        bus.emit(EventContext(
            game_state=state,
            event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "emergency_cache_lv0"},
        ))
        assert inv.actions_remaining == 2
