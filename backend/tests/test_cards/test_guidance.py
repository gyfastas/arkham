"""Tests for Guidance (Level 0).

官方：选择你所在地点1位本回合尚未执行回合的其他调查员。
该调查员在其本回合中可执行额外1个行动。
"""

import pytest

from backend.cards.seeker.guidance_lv0 import Guidance
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

    loc_data = make_location_data(id="loc_a")
    state.card_database[loc_data.id] = loc_data
    state.locations["loc_a"] = LocationState(
        location_id="loc_a", card_data=loc_data)

    inv1_data = make_investigator_data(id="inv1_data", name="Seeker")
    inv2_data = make_investigator_data(id="inv2_data", name="Guardian")
    state.card_database[inv1_data.id] = inv1_data
    state.card_database[inv2_data.id] = inv2_data
    inv1 = InvestigatorState(
        investigator_id="inv1", card_data=inv1_data, location_id="loc_a")
    inv2 = InvestigatorState(
        investigator_id="inv2", card_data=inv2_data, location_id="loc_a")
    state.investigators["inv1"] = inv1
    state.investigators["inv2"] = inv2

    impl = Guidance("guidance_temp")
    impl.register(bus, "guidance_temp")
    return state, bus, inv1, inv2, impl


def _play(state, bus, extra=None):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "guidance_lv0", **(extra or {})},
    )
    bus.emit(ctx)
    return ctx


def _begin_turn(state, bus, inv_id):
    inv = state.get_investigator(inv_id)
    inv.actions_remaining = 3  # 引擎先发放3行动
    ctx = EventContext(
        game_state=state,
        event=GameEvent.INVESTIGATOR_TURN_BEGINS,
        investigator_id=inv_id,
    )
    bus.emit(ctx)
    return ctx


class TestGuidance:
    def test_grants_extra_action_to_target(self, setup):
        """默认选择同地点尚未行动的另一调查员；其回合开始+1行动。"""
        state, bus, inv1, inv2, impl = setup
        ctx = _play(state, bus)
        assert ctx.extra["guidance_target"] == "inv2"

        _begin_turn(state, bus, "inv2")
        assert inv2.actions_remaining == 4

    def test_target_who_already_took_turn_not_eligible(self, setup):
        """本回合已行动的调查员不是合法目标。"""
        state, bus, inv1, inv2, impl = setup
        inv2.has_taken_turn = True
        ctx = _play(state, bus)
        assert "guidance_target" not in ctx.extra

        _begin_turn(state, bus, "inv2")
        assert inv2.actions_remaining == 3

    def test_explicit_target(self, setup):
        state, bus, inv1, inv2, impl = setup
        ctx = _play(state, bus, extra={"target_investigator": "inv2"})
        assert ctx.extra["guidance_target"] == "inv2"

    def test_no_extra_action_for_self_turn(self, setup):
        """打出者自己的回合开始不获得额外行动。"""
        state, bus, inv1, inv2, impl = setup
        _play(state, bus)
        _begin_turn(state, bus, "inv1")
        assert inv1.actions_remaining == 3

    def test_solo_no_target(self, setup):
        """单人局没有其他调查员：效果不生效。"""
        state, bus, inv1, inv2, impl = setup
        state.investigators.pop("inv2")
        ctx = _play(state, bus)
        assert "guidance_target" not in ctx.extra
