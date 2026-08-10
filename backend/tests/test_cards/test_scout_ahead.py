"""Tests for Scout Ahead (Level 0)."""

import pytest

from backend.cards.rogue.scout_ahead_lv0 import ScoutAhead
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    # 链式地点：loc1 - loc2 - loc3 - loc4
    conns = {
        "loc1": ["loc2"],
        "loc2": ["loc1", "loc3"],
        "loc3": ["loc2", "loc4"],
        "loc4": ["loc3"],
    }
    for loc_id, links in conns.items():
        ld = make_location_data(id=loc_id, connections=links)
        state.card_database[loc_id] = ld
        state.locations[loc_id] = LocationState(location_id=loc_id, card_data=ld)
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    state.investigators["inv1"] = inv
    impl = ScoutAhead("scout_inst")
    impl.register(bus, "scout_inst")
    return state, bus, inv


def _play(bus, state, **extra):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "scout_ahead_lv0", **extra},
    )
    bus.emit(ctx)
    return ctx


class TestScoutAhead:
    def test_auto_route_moves_three_times(self, setup):
        state, bus, inv = setup
        ctx = _play(bus, state)
        assert inv.location_id == "loc4"
        assert ctx.extra["scout_ahead_moved"] == ["loc2", "loc3", "loc4"]

    def test_explicit_destinations(self, setup):
        state, bus, inv = setup
        ctx = _play(bus, state, destinations=["loc2"])
        assert inv.location_id == "loc2"
        assert ctx.extra["scout_ahead_moved"] == ["loc2"]

    def test_unconnected_destination_stops_route(self, setup):
        state, bus, inv = setup
        ctx = _play(bus, state, destinations=["loc2", "loc4"])
        # loc4 不与 loc2 直连：第二步失败，停在 loc2
        assert inv.location_id == "loc2"
        assert ctx.extra["scout_ahead_moved"] == ["loc2"]

    def test_dead_end_no_move(self, setup):
        """孤立地点：无处可去。"""
        state, bus, inv = setup
        state.locations["loc1"].card_data.connections = []
        ctx = _play(bus, state)
        assert inv.location_id == "loc1"
        assert "scout_ahead_moved" not in ctx.extra
