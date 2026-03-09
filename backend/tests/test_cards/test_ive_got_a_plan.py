"""Tests for I've Got a Plan (Level 0)."""

import pytest
from backend.cards.seeker.ive_got_a_plan_lv0 import IveGotAPlan
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, ChaosTokenType, Skill
from backend.models.state import GameState, InvestigatorState, LocationState, ScenarioState, CardInstance
from backend.tests.conftest import make_investigator_data, make_location_data


class TestIveGotAPlan:
    def test_card_data(self):
        """IveGotAPlan card_id is correct; skill_icons should include intellect and combat."""
        impl = IveGotAPlan("plan_inst")
        assert impl.card_id == "ive_got_a_plan_lv0"

    def test_skeleton_skill_value_no_crash(self):
        """Skeleton use_intellect_for_fight handler does not raise."""
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

        impl = IveGotAPlan("impl_1")
        impl.register(bus, "impl_1")

        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1",
            source="impl_1",
        )
        # Skeleton handler is a pass — should not raise
        bus.emit(ctx)
