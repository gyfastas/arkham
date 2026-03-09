"""Tests for Drawn to the Flame (Level 0)."""

import pytest
from backend.cards.mystic.drawn_to_the_flame_lv0 import DrawnToTheFlame
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import make_event_data, make_investigator_data, make_location_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data

    card_data = make_event_data(
        id="drawn_to_the_flame_lv0", name="Drawn to the Flame",
    )
    state.card_database["drawn_to_the_flame_lv0"] = card_data

    loc_data = make_location_data(shroud=2)
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="test_location",
        deck=["card_a", "card_b"],
    )
    state.investigators["inv1"] = inv

    loc = LocationState(location_id="test_location", card_data=loc_data, clues=3)
    state.locations["test_location"] = loc

    impl = DrawnToTheFlame("inst_dttf")
    impl.register(bus, "inst_dttf")

    return state, bus, inv, loc


class TestDrawnToTheFlame:
    def test_card_id(self, setup):
        assert DrawnToTheFlame.card_id == "drawn_to_the_flame_lv0"

    def test_discover_2_clues(self, setup):
        """Playing Drawn to the Flame discovers 2 clues at your location."""
        state, bus, inv, loc = setup
        initial_clues = inv.clues
        initial_loc_clues = loc.clues

        ctx = EventContext(
            event=GameEvent.CARD_PLAYED,
            game_state=state,
            investigator_id="inv1",
            extra={"card_id": "drawn_to_the_flame_lv0"},
        )
        bus.emit(ctx)

        assert inv.clues == initial_clues + 2
        assert loc.clues == initial_loc_clues - 2
