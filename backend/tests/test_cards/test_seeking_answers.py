"""Tests for Seeking Answers (Level 0)."""

import pytest
from backend.cards.seeker.seeking_answers_lv0 import SeekingAnswers
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, ChaosTokenType, Skill
from backend.models.state import GameState, InvestigatorState, LocationState, ScenarioState, CardInstance
from backend.tests.conftest import make_investigator_data, make_location_data


class TestSeekingAnswers:
    def test_card_data(self):
        """SeekingAnswers has the correct card_id."""
        impl = SeekingAnswers("seeking_inst")
        assert impl.card_id == "seeking_answers_lv0"

    def test_skeleton_no_crash(self):
        """Skeleton handler does not raise on successful intellect test event."""
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

        impl = SeekingAnswers("impl_1")
        impl.register(bus, "impl_1")

        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1",
        )
        # Skeleton handler is mostly a pass — should not raise
        bus.emit(ctx)
        # No clues moved since skeleton is not yet implemented
        assert loc.clues == 3
