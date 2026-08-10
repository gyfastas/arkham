"""Tests for Well Connected (Level 0)."""

import pytest

from backend.cards.rogue.well_connected_lv0 import WellConnected
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    inv.resources = 12
    state.investigators["inv1"] = inv
    inst = CardInstance(
        instance_id="wc_inst", card_id="well_connected_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["wc_inst"] = inst
    inv.play_area.append("wc_inst")
    impl = WellConnected("wc_inst")
    impl.register(bus, "wc_inst")
    return state, bus, inv, inst, impl


def _skill_value(bus, state, amount=3):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1",
        skill_type=Skill.WILLPOWER,
        amount=amount,
    )
    bus.emit(ctx)
    return ctx


class TestWellConnected:
    def test_exhaust_grants_bonus_per_five_resources(self, setup):
        state, bus, inv, inst, impl = setup
        assert impl.activate(state, "inv1") is True
        assert inst.exhausted is True
        ctx = _skill_value(bus, state)
        assert ctx.amount == 5  # 12资源 // 5 = +2
        assert ctx.extra["well_connected_bonus"] == 2

    def test_bonus_scales_with_resources(self, setup):
        state, bus, inv, inst, impl = setup
        inv.resources = 4
        impl.activate(state, "inv1")
        ctx = _skill_value(bus, state)
        assert ctx.amount == 3  # 4资源 // 5 = 0

    def test_cannot_activate_twice(self, setup):
        state, bus, inv, inst, impl = setup
        assert impl.activate(state, "inv1") is True
        assert impl.activate(state, "inv1") is False

    def test_cleared_after_test(self, setup):
        state, bus, inv, inst, impl = setup
        impl.activate(state, "inv1")
        bus.emit(EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1",
        ))
        ctx = _skill_value(bus, state)
        assert ctx.amount == 3

    def test_not_armed_no_bonus(self, setup):
        state, bus, inv, inst, impl = setup
        ctx = _skill_value(bus, state)
        assert ctx.amount == 3
