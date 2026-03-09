"""Tests for You Handle This One! (Level 0)."""

import pytest
from backend.cards.rogue.you_handle_this_one_lv0 import YouHandleThisOne
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_investigator_data, make_event_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data

    card_data = make_event_data(id="you_handle_this_one_lv0")
    state.card_database["you_handle_this_one_lv0"] = card_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
    )
    inv.resources = 3
    state.investigators["inv1"] = inv

    impl = YouHandleThisOne("yhto_impl")
    impl.register(bus, "yhto_impl")

    return state, bus, inv


class TestYouHandleThisOne:
    def test_card_registered(self, setup):
        """Implementation class exists and has correct card_id."""
        assert YouHandleThisOne.card_id == "you_handle_this_one_lv0"

    def test_gain_resource_on_play(self, setup):
        """Playing the card grants 1 resource."""
        state, bus, inv = setup
        initial_resources = inv.resources

        ctx = EventContext(
            game_state=state,
            event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "you_handle_this_one_lv0"},
        )
        bus.emit(ctx)

        assert inv.resources == initial_resources + 1

    def test_no_resource_for_other_cards(self, setup):
        """Playing a different card does not grant resource."""
        state, bus, inv = setup
        initial_resources = inv.resources

        ctx = EventContext(
            game_state=state,
            event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "other_card"},
        )
        bus.emit(ctx)

        assert inv.resources == initial_resources
