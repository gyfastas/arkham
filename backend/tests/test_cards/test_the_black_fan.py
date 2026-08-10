"""Tests for The Black Fan (Level 3)."""

import pytest

from backend.cards.rogue.the_black_fan_lv3 import TheBlackFan
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
    inv_data = make_investigator_data(health=7, sanity=7)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    inv.resources = 9
    state.investigators["inv1"] = inv
    inst = CardInstance(
        instance_id="fan_inst", card_id="the_black_fan_lv3",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["fan_inst"] = inst
    inv.play_area.append("fan_inst")
    impl = TheBlackFan("fan_inst")
    impl.register(bus, "fan_inst")
    return state, bus, inv, impl


def _gain(bus, state, amount):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.RESOURCES_GAINED,
        investigator_id="inv1",
        amount=amount,
    )
    bus.emit(ctx)


class TestTheBlackFan:
    def test_ten_resources_grant_health_sanity(self, setup):
        state, bus, inv, impl = setup
        inv.resources = 10
        _gain(bus, state, 1)
        assert inv.health_bonus == 1
        assert inv.sanity_bonus == 1
        assert inv.health == 8 and inv.sanity == 8

    def test_bonus_removed_below_ten(self, setup):
        state, bus, inv, impl = setup
        inv.resources = 10
        _gain(bus, state, 1)
        inv.resources = 9
        bus.emit(EventContext(
            game_state=state,
            event=GameEvent.RESOURCES_SPENT,
            investigator_id="inv1",
            amount=1,
        ))
        assert inv.health_bonus == 0
        assert inv.sanity_bonus == 0

    def test_fifteen_resources_extra_action(self, setup):
        state, bus, inv, impl = setup
        inv.resources = 15
        inv.actions_remaining = 3
        ctx = EventContext(
            game_state=state,
            event=GameEvent.INVESTIGATOR_TURN_BEGINS,
            investigator_id="inv1",
        )
        bus.emit(ctx)
        assert inv.actions_remaining == 4
        assert ctx.extra["black_fan_extra_action"] is True

    def test_no_extra_action_below_fifteen(self, setup):
        state, bus, inv, impl = setup
        inv.resources = 14
        inv.actions_remaining = 3
        bus.emit(EventContext(
            game_state=state,
            event=GameEvent.INVESTIGATOR_TURN_BEGINS,
            investigator_id="inv1",
        ))
        assert inv.actions_remaining == 3

    def test_twenty_resources_skill_bonus(self, setup):
        state, bus, inv, impl = setup
        inv.resources = 20
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 4

    def test_no_skill_bonus_below_twenty(self, setup):
        state, bus, inv, impl = setup
        inv.resources = 19
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 3
