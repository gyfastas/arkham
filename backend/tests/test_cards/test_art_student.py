"""Tests for Art Student (Level 0)."""

import pytest
from backend.cards.seeker.art_student_lv0 import ArtStudent
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, ChaosTokenType, Skill
from backend.models.state import GameState, InvestigatorState, LocationState, ScenarioState, CardInstance
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def setup():
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
        deck=["c1", "c2", "c3", "c4", "c5"],
    )
    state.investigators["inv1"] = inv
    loc = LocationState(location_id="test_location", card_data=loc_data, clues=3)
    state.locations["test_location"] = loc
    return state, bus, inv, loc


class TestArtStudent:
    def test_discovers_clue_on_enter(self, setup):
        """Art Student discovers 1 clue at location when entering play."""
        state, bus, inv, loc = setup
        inst_id = "inst_1"
        ci = CardInstance(
            instance_id=inst_id,
            card_id="art_student_lv0",
            owner_id="inv1",
            controller_id="inv1",
        )
        state.cards_in_play[inst_id] = ci
        inv.play_area.append(inst_id)

        impl = ArtStudent(inst_id)
        impl.register(bus, inst_id)

        initial_inv_clues = inv.clues
        initial_loc_clues = loc.clues

        ctx = EventContext(
            game_state=state,
            event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1",
            target=inst_id,
        )
        bus.emit(ctx)

        assert inv.clues == initial_inv_clues + 1
        assert loc.clues == initial_loc_clues - 1

    def test_no_clue_if_none(self, setup):
        """No clue discovered when location has 0 clues."""
        state, bus, inv, loc = setup
        loc.clues = 0

        inst_id = "inst_1"
        ci = CardInstance(
            instance_id=inst_id,
            card_id="art_student_lv0",
            owner_id="inv1",
            controller_id="inv1",
        )
        state.cards_in_play[inst_id] = ci
        inv.play_area.append(inst_id)

        impl = ArtStudent(inst_id)
        impl.register(bus, inst_id)

        ctx = EventContext(
            game_state=state,
            event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1",
            target=inst_id,
        )
        bus.emit(ctx)

        assert inv.clues == 0
        assert loc.clues == 0
