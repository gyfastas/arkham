"""Tests for Hot Streak (Level 4)."""

import pytest
from backend.cards.rogue.hot_streak_lv4 import HotStreak
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

    card_data = make_event_data(id="hot_streak_lv4")
    state.card_database["hot_streak_lv4"] = card_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
    )
    inv.resources = 0
    state.investigators["inv1"] = inv

    impl = HotStreak("hs_inst")
    impl.register(bus, "hs_inst")
    return state, bus, inv, impl


class TestHotStreak:
    def test_gain_10_resources(self, setup):
        """Hot Streak grants 10 resources when played."""
        state, bus, inv, impl = setup

        ctx = EventContext(
            game_state=state,
            event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "hot_streak_lv4"},
        )
        bus.emit(ctx)

        assert inv.resources == 10

    def test_no_resources_for_other_cards(self, setup):
        """Playing a different card does not grant resources."""
        state, bus, inv, impl = setup

        ctx = EventContext(
            game_state=state,
            event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "other_card"},
        )
        bus.emit(ctx)

        assert inv.resources == 0
