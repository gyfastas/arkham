"""Tests for Ríastrad (Level 1)."""

import pytest

from backend.cards.rogue.ríastrad_lv1 import Riastrad
from backend.engine.event_bus import EventBus, EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(1)
    inv_data = make_investigator_data(combat=3)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    state.investigators["inv1"] = inv
    impl = Riastrad("riastrad_inst")
    impl.register(bus, "riastrad_inst")
    impl.bind_chaos_bag(bag)
    return state, bus, bag, inv


def _play(bus, state, **extra):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "ríastrad_lv1", **extra},
    )
    bus.emit(ctx)
    return ctx


class TestRiastrad:
    def test_default_adds_three_curses(self, setup):
        state, bus, bag, inv = setup
        before = bag.tokens.count(ChaosTokenType.CURSE)
        ctx = _play(bus, state)
        assert ctx.extra["riastrad_curses"] == 3
        assert bag.tokens.count(ChaosTokenType.CURSE) == before + 3

    def test_combat_bonus_and_bonus_damage(self, setup):
        state, bus, bag, inv = setup
        _play(bus, state)
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 6  # +3 combat

        ctx2 = EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            success=True,
            modified_skill=6,
            difficulty=3,
        )
        bus.emit(ctx2)
        assert ctx2.extra["bonus_damage"] == 3

    def test_explicit_curse_count(self, setup):
        state, bus, bag, inv = setup
        before = bag.tokens.count(ChaosTokenType.CURSE)
        ctx = _play(bus, state, curse_count=1)
        assert bag.tokens.count(ChaosTokenType.CURSE) == before + 1
        ctx2 = EventContext(
            game_state=state,
            event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            amount=3,
        )
        bus.emit(ctx2)
        assert ctx2.amount == 4

    def test_cleared_after_test(self, setup):
        state, bus, bag, inv = setup
        _play(bus, state)
        bus.emit(EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1",
            success=True,
        ))
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 3

    def test_non_combat_untouched(self, setup):
        state, bus, bag, inv = setup
        _play(bus, state)
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1",
            skill_type=Skill.AGILITY,
            amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 3
