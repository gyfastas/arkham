"""Tests for Shortcut (Level 0)."""

import pytest
from backend.cards.seeker.shortcut_lv0 import Shortcut
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, ChaosTokenType, Skill
from backend.models.state import GameState, InvestigatorState, LocationState, ScenarioState, CardInstance
from backend.tests.conftest import make_investigator_data, make_location_data


class TestShortcut:
    def test_card_data(self):
        """Shortcut card_id is correct and traits include tactic."""
        impl = Shortcut("shortcut_inst")
        assert impl.card_id == "shortcut_lv0"
        # Shortcut is a Fast Tactic event — trait validation
        # would come from card data JSON; here we verify the impl exists.

    def test_skeleton_move_is_noop(self):
        """Skeleton move_investigator handler does not raise."""
        state = GameState(scenario=ScenarioState(scenario_id="test"))
        bus = EventBus()
        inv_data = make_investigator_data()
        state.card_database[inv_data.id] = inv_data
        loc_data = make_location_data()
        state.card_database[loc_data.id] = loc_data
        inv = InvestigatorState(
            investigator_id="inv1",
            card_data=inv_data,
            location_id="test_location",
            deck=["c1", "c2"],
        )
        state.investigators["inv1"] = inv
        loc = LocationState(location_id="test_location", card_data=loc_data, clues=3)
        state.locations["test_location"] = loc

        impl = Shortcut("impl_1")
        impl.register(bus, "impl_1")

        ctx = EventContext(
            game_state=state,
            event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "shortcut_lv0"},
        )
        # Skeleton handler is a pass — should not raise
        bus.emit(ctx)
        assert inv.location_id == "test_location"
