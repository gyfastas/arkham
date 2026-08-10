"""Tests for Charon's Obol (Level 1)."""

import pytest
from backend.cards.rogue.charons_obol_lv1 import CharonsObol
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
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
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv

    ci = CardInstance(
        instance_id="obol_inst", card_id="charons_obol_lv1",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["obol_inst"] = ci
    inv.play_area.append("obol_inst")

    impl = CharonsObol("obol_inst")
    impl.register(bus, "obol_inst")
    return state, bus, inv, impl, ci


def _defeated(bus, state):
    bus.emit(EventContext(
        game_state=state, event=GameEvent.INVESTIGATOR_DEFEATED,
        investigator_id="inv1",
    ))


class TestCharonsObol:
    def test_card_id(self):
        assert CharonsObol.card_id == "charons_obol_lv1"

    def test_defeat_is_recorded(self, setup):
        """Being defeated during the scenario is tracked in scenario vars."""
        state, bus, inv, impl, ci = setup
        _defeated(bus, state)
        assert state.scenario.vars["charons_obol"]["defeated"] == ["inv1"]

    def test_no_record_without_obol_in_play(self, setup):
        state, bus, inv, impl, ci = setup
        inv.play_area.remove("obol_inst")
        _defeated(bus, state)
        assert "charons_obol" not in state.scenario.vars

    def test_xp_bonus_when_not_defeated(self, setup):
        """Not defeated during the scenario: earn 2 additional XP."""
        state, bus, inv, impl, ci = setup
        xp = impl.apply_scenario_xp(state, "inv1", 5)
        assert xp == 7
        assert "killed" not in state.scenario.vars["charons_obol"]

    def test_killed_when_defeated(self, setup):
        """Defeated during the scenario: killed, no bonus XP."""
        state, bus, inv, impl, ci = setup
        _defeated(bus, state)
        xp = impl.apply_scenario_xp(state, "inv1", 5)
        assert xp == 5
        assert state.scenario.vars["charons_obol"]["killed"] == ["inv1"]
