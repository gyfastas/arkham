"""Tests for Pay Day (Level 1)."""

import pytest

from backend.cards.rogue.pay_day_lv1 import PayDay
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
    inv.resources = 2
    state.investigators["inv1"] = inv
    impl = PayDay("pay_day_inst")
    impl.register(bus, "pay_day_inst")
    return state, bus, inv


def _play(bus, state, **extra):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "pay_day_lv1", **extra},
    )
    bus.emit(ctx)
    return ctx


class TestPayDay:
    def test_first_action_gains_one_and_ends_turn(self, setup):
        """Played as the first action: gain 1 resource, turn ends."""
        state, bus, inv = setup
        inv.actions_remaining = 3
        ctx = _play(bus, state)
        assert ctx.extra["pay_day_gained"] == 1
        assert inv.resources == 3
        assert inv.actions_remaining == 0
        assert ctx.extra["pay_day_ended_turn"] is True

    def test_third_action_gains_three(self, setup):
        """Played as the third action: gain 3 resources."""
        state, bus, inv = setup
        inv.actions_remaining = 1  # two actions already performed
        ctx = _play(bus, state)
        assert ctx.extra["pay_day_gained"] == 3
        assert inv.resources == 5
        assert inv.actions_remaining == 0

    def test_explicit_action_count_override(self, setup):
        """Session may pass the real per-turn action count (e.g. extra actions)."""
        state, bus, inv = setup
        inv.actions_remaining = 2
        ctx = _play(bus, state, actions_this_turn=4)
        assert ctx.extra["pay_day_gained"] == 4
        assert inv.resources == 6

    def test_other_card_ignored(self, setup):
        state, bus, inv = setup
        bus.emit(EventContext(
            game_state=state,
            event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "emergency_cache_lv0"},
        ))
        assert inv.resources == 2
