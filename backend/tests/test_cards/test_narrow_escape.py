"""Tests for Narrow Escape (Level 0)."""

import pytest
from backend.cards.rogue.narrow_escape_lv0 import NarrowEscape
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_event_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    state.card_database["narrow_escape_lv0"] = make_event_data(
        id="narrow_escape_lv0", cost=0, fast=True,
    )

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        hand=["narrow_escape_lv0"], resources=2,
    )
    state.investigators["inv1"] = inv

    impl = NarrowEscape("ne_inst")
    impl.register(bus, "ne_inst")
    return state, bus, inv, impl


def _aoo(bus, state):
    ctx = EventContext(
        game_state=state, event=GameEvent.ATTACK_OF_OPPORTUNITY,
        investigator_id="inv1", enemy_id="enemy_1",
    )
    bus.emit(ctx)
    return ctx


def _value_ctx(state, amount=3):
    return EventContext(
        game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1", skill_type=Skill.COMBAT, amount=amount,
    )


class TestNarrowEscape:
    def test_card_id(self):
        assert NarrowEscape.card_id == "narrow_escape_lv0"

    def test_cancels_attack_of_opportunity(self, setup):
        """Played when an enemy makes an AoO against you: cancel it."""
        state, bus, inv, impl = setup
        ctx = _aoo(bus, state)

        assert ctx.cancelled is True
        assert "narrow_escape_lv0" not in inv.hand
        assert "narrow_escape_lv0" in inv.discard
        assert ctx.extra["narrow_escape_cancelled"] is True

    def test_next_skill_test_gets_plus_2(self, setup):
        state, bus, inv, impl = setup
        _aoo(bus, state)

        ctx = _value_ctx(state, amount=3)
        bus.emit(ctx)
        assert ctx.amount == 5

    def test_boost_is_one_shot(self, setup):
        state, bus, inv, impl = setup
        _aoo(bus, state)

        bus.emit(_value_ctx(state, amount=3))
        ctx2 = _value_ctx(state, amount=3)
        bus.emit(ctx2)
        assert ctx2.amount == 3  # second test: no bonus

    def test_boost_expires_at_turn_end(self, setup):
        state, bus, inv, impl = setup
        _aoo(bus, state)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="inv1",
        ))
        ctx = _value_ctx(state, amount=3)
        bus.emit(ctx)
        assert ctx.amount == 3

    def test_no_trigger_without_card(self, setup):
        state, bus, inv, impl = setup
        inv.hand.remove("narrow_escape_lv0")
        ctx = _aoo(bus, state)
        assert ctx.cancelled is False
