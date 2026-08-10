"""Tests for Precious Memento (Level 4)."""

import pytest

from backend.cards.rogue.precious_memento_lv4 import PreciousMemento
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
    state.investigators["inv1"] = inv
    inst = CardInstance(
        instance_id="memento_inst", card_id="precious_memento_lv4",
        owner_id="inv1", controller_id="inv1", damage=1, horror=1,
    )
    state.cards_in_play["memento_inst"] = inst
    inv.play_area.append("memento_inst")
    impl = PreciousMemento("memento_inst")
    impl.register(bus, "memento_inst")
    return state, bus, inv, inst


def _result(bus, state, event, modified, difficulty):
    ctx = EventContext(
        game_state=state,
        event=event,
        investigator_id="inv1",
        skill_type=Skill.WILLPOWER,
        success=event == GameEvent.SKILL_TEST_SUCCESSFUL,
        modified_skill=modified,
        difficulty=difficulty,
    )
    bus.emit(ctx)
    return ctx


class TestPreciousMemento:
    def test_fail_by_two_heals_horror(self, setup):
        state, bus, inv, inst = setup
        ctx = _result(bus, state, GameEvent.SKILL_TEST_FAILED, 1, 3)
        assert ctx.extra["precious_memento_healed_horror"] is True
        assert inst.horror == 0
        assert inst.exhausted is True
        assert inst.damage == 1  # damage untouched

    def test_succeed_by_two_heals_damage(self, setup):
        state, bus, inv, inst = setup
        ctx = _result(bus, state, GameEvent.SKILL_TEST_SUCCESSFUL, 5, 3)
        assert ctx.extra["precious_memento_healed_damage"] is True
        assert inst.damage == 0
        assert inst.exhausted is True

    def test_margin_one_no_trigger(self, setup):
        state, bus, inv, inst = setup
        _result(bus, state, GameEvent.SKILL_TEST_FAILED, 2, 3)
        assert inst.horror == 1 and not inst.exhausted
        _result(bus, state, GameEvent.SKILL_TEST_SUCCESSFUL, 4, 3)
        assert inst.damage == 1 and not inst.exhausted

    def test_nothing_to_heal_no_trigger(self, setup):
        """No horror/damage on the memento: reaction is not wasted."""
        state, bus, inv, inst = setup
        inst.horror = 0
        inst.damage = 0
        _result(bus, state, GameEvent.SKILL_TEST_FAILED, 0, 3)
        _result(bus, state, GameEvent.SKILL_TEST_SUCCESSFUL, 5, 3)
        assert not inst.exhausted

    def test_not_in_play_no_trigger(self, setup):
        state, bus, inv, inst = setup
        inv.play_area.remove("memento_inst")
        _result(bus, state, GameEvent.SKILL_TEST_FAILED, 0, 3)
        assert inst.horror == 1
