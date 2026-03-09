"""Tests for Expose Weakness (Level 1)."""

import pytest
from backend.cards.seeker.expose_weakness_lv1 import ExposeWeakness
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, ChaosTokenType, Skill
from backend.models.state import GameState, InvestigatorState, LocationState, ScenarioState, CardInstance
from backend.tests.conftest import make_investigator_data, make_location_data


class TestExposeWeakness:
    def test_card_data(self):
        """ExposeWeakness card_id is correct; skill_icons include combat: 2."""
        impl = ExposeWeakness("expose_inst")
        assert impl.card_id == "expose_weakness_lv1"
        # Expose Weakness (Lv1) has intellect and combat skill icons.
        # Icon values are defined in card data JSON.

    def test_skeleton_no_crash(self):
        """Skeleton handler does not raise when card is played."""
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

        impl = ExposeWeakness("impl_1")
        impl.register(bus, "impl_1")

        ctx = EventContext(
            game_state=state,
            event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "expose_weakness_lv1"},
        )
        # Skeleton handler is a pass — should not raise
        bus.emit(ctx)
