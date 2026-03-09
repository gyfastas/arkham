"""Tests for Working a Hunch (Level 0)."""

import pytest
from backend.cards.seeker.working_a_hunch_lv0 import WorkingAHunch
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import GameState, InvestigatorState, LocationState, ScenarioState
from backend.tests.conftest import make_investigator_data, make_location_data, make_event_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data

    hunch_data = make_event_data(
        id="working_a_hunch_lv0", name="Working a Hunch",
        fast=True,
    )
    state.card_database["working_a_hunch_lv0"] = hunch_data

    loc_data = make_location_data(shroud=2)
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="test_location",
        deck=[],
    )
    state.investigators["inv1"] = inv

    loc = LocationState(location_id="test_location", card_data=loc_data, clues=3)
    state.locations["test_location"] = loc

    impl = WorkingAHunch("inst_hunch")
    impl.register(bus, "inst_hunch")

    return state, bus, inv, loc


class TestWorkingAHunch:
    def test_discovers_clue_on_play(self, setup):
        """Playing Working a Hunch discovers 1 clue at current location."""
        state, bus, inv, loc = setup
        initial_inv_clues = inv.clues
        initial_loc_clues = loc.clues

        ctx = EventContext(
            game_state=state,
            event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "working_a_hunch_lv0"},
        )
        bus.emit(ctx)

        assert inv.clues == initial_inv_clues + 1
        assert loc.clues == initial_loc_clues - 1

    def test_no_clue_if_none_left(self, setup):
        """If location has 0 clues, playing Working a Hunch does nothing."""
        state, bus, inv, loc = setup
        loc.clues = 0

        ctx = EventContext(
            game_state=state,
            event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "working_a_hunch_lv0"},
        )
        bus.emit(ctx)

        assert inv.clues == 0
        assert loc.clues == 0
