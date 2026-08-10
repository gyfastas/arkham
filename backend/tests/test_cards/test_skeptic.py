"""Tests for Skeptic (Level 1)."""

import pytest

from backend.cards.rogue.skeptic_lv1 import Skeptic
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill
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
    state.investigators["inv1"] = inv
    impl = Skeptic("skeptic_inst")
    impl.register(bus, "skeptic_inst")
    return state, bus, inv


def _commit(bus, state, cards=("skeptic_lv1",)):
    bus.emit(EventContext(
        game_state=state,
        event=GameEvent.SKILL_TEST_COMMIT,
        investigator_id="inv1",
        skill_type=Skill.WILLPOWER,
        difficulty=3,
        committed_cards=list(cards),
        amount=1,
    ))


def _resolve(bus, state, token, modifier):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CHAOS_TOKEN_RESOLVED,
        investigator_id="inv1",
        chaos_token=token,
        amount=modifier,
        skill_type=Skill.WILLPOWER,
        difficulty=3,
    )
    bus.emit(ctx)
    return ctx


class TestSkeptic:
    def test_curse_becomes_plus_one(self, setup):
        state, bus, inv = setup
        _commit(bus, state)
        ctx = _resolve(bus, state, ChaosTokenType.CURSE, -2)
        assert ctx.amount == 1
        assert ctx.extra["skeptic_applied"] is True

    def test_bless_becomes_plus_one(self, setup):
        state, bus, inv = setup
        _commit(bus, state)
        ctx = _resolve(bus, state, ChaosTokenType.BLESS, 2)
        assert ctx.amount == 1

    def test_numeric_token_untouched(self, setup):
        state, bus, inv = setup
        _commit(bus, state)
        ctx = _resolve(bus, state, ChaosTokenType.MINUS_3, -3)
        assert ctx.amount == -3
        assert "skeptic_applied" not in ctx.extra

    def test_not_committed_no_effect(self, setup):
        state, bus, inv = setup
        _commit(bus, state, cards=("guts_lv0",))
        ctx = _resolve(bus, state, ChaosTokenType.CURSE, -2)
        assert ctx.amount == -2

    def test_cleared_after_test(self, setup):
        state, bus, inv = setup
        _commit(bus, state)
        bus.emit(EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1",
        ))
        ctx = _resolve(bus, state, ChaosTokenType.CURSE, -2)
        assert ctx.amount == -2
