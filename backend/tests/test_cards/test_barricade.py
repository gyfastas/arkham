"""Tests for Barricade (Level 0)."""

import pytest
from backend.cards.seeker.barricade_lv0 import Barricade
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    barricade_data = make_event_data(id="barricade_lv0", name="Barricade")
    state.card_database["barricade_lv0"] = barricade_data

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    loc_a = make_location_data(id="loc_a", connections=["loc_b"])
    loc_b = make_location_data(id="loc_b", connections=["loc_a"])
    state.card_database["loc_a"] = loc_a
    state.card_database["loc_b"] = loc_b

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc_a",
    )
    state.investigators["inv1"] = inv
    state.locations["loc_a"] = LocationState(location_id="loc_a", card_data=loc_a, clues=0)
    state.locations["loc_b"] = LocationState(location_id="loc_b", card_data=loc_b, clues=0)

    impl = Barricade("inst_barricade")
    impl.register(bus, "inst_barricade")

    return state, bus, inv, impl


def _play(state, bus):
    ctx = EventContext(
        game_state=state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "barricade_lv0"},
    )
    bus.emit(ctx)
    return ctx


class TestBarricade:
    def test_attach_marks_location(self, setup):
        """打出后：所在地点记入 barricaded_locations（供生成/移动钩子查询）。"""
        state, bus, inv, impl = setup
        ctx = _play(state, bus)
        assert ctx.extra["barricaded_location"] == "loc_a"
        assert state.scenario.vars["barricaded_locations"] == ["loc_a"]

    def test_discard_when_investigator_leaves(self, setup):
        """强制：调查员离开被附加地点时弃掉屏障（从记录中移除）。"""
        state, bus, inv, impl = setup
        _play(state, bus)

        # 移动行动发起（MOVE_ACTION_INITIATED 在移动生效前发出）
        ctx = EventContext(
            game_state=state, event=GameEvent.MOVE_ACTION_INITIATED,
            investigator_id="inv1", location_id="loc_b",
        )
        bus.emit(ctx)

        assert ctx.extra.get("barricade_discarded") == "loc_a"
        assert state.scenario.vars["barricaded_locations"] == []

    def test_no_discard_when_leaving_other_location(self, setup):
        """调查员从其他地点移动：不弃掉屏障。"""
        state, bus, inv, impl = setup
        _play(state, bus)
        inv.location_id = "loc_b"  # 调查员已不在被附加地点

        ctx = EventContext(
            game_state=state, event=GameEvent.MOVE_ACTION_INITIATED,
            investigator_id="inv1", location_id="loc_a",
        )
        bus.emit(ctx)

        assert "barricade_discarded" not in ctx.extra
        assert state.scenario.vars["barricaded_locations"] == ["loc_a"]

    def test_other_card_played_does_not_attach(self, setup):
        state, bus, inv, impl = setup
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "some_other_card"},
        )
        bus.emit(ctx)
        assert "barricaded_locations" not in state.scenario.vars
