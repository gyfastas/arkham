"""Tests for Burglary (Level 0)."""

import pytest
from backend.cards.rogue.burglary_lv0 import Burglary
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(intellect=3, agility=5)
    state.card_database[inv_data.id] = inv_data

    loc_data = make_location_data(id="loc1")
    state.card_database["loc1"] = loc_data
    state.locations["loc1"] = LocationState(
        location_id="loc1", card_data=loc_data, clues=2, revealed=True,
    )

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
    )
    inv.resources = 5
    state.investigators["inv1"] = inv

    impl = Burglary("burglary_inst")
    impl.register(bus, "burglary_inst")

    ci = CardInstance(
        instance_id="burglary_inst", card_id="burglary_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["burglary_inst"] = ci
    inv.play_area.append("burglary_inst")
    return state, bus, inv, impl, ci


class TestBurglary:
    def test_card_id(self, setup):
        """Burglary has correct card_id."""
        assert Burglary.card_id == "burglary_lv0"

    def test_activate_exhausts(self, setup):
        """Activating Burglary exhausts it."""
        state, bus, inv, impl, ci = setup
        assert impl.activate(state, "inv1") is True
        assert ci.exhausted is True

    def test_activate_fails_when_exhausted(self, setup):
        state, bus, inv, impl, ci = setup
        ci.exhausted = True
        assert impl.activate(state, "inv1") is False

    def test_no_agility_substitution(self, setup):
        """Official text has no agility-for-intellect substitution."""
        state, bus, inv, impl, ci = setup
        impl.activate(state, "inv1")

        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1",
            skill_type=Skill.INTELLECT,
            amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 3  # unchanged

    def test_resources_instead_of_clues(self, setup):
        """On success, gain 3 resources instead of discovering a clue."""
        state, bus, inv, impl, ci = setup
        impl.activate(state, "inv1")

        # Simulate the engine having just discovered a clue
        loc = state.locations["loc1"]
        loc.clues -= 1
        inv.clues += 1

        ctx = EventContext(
            game_state=state,
            event=GameEvent.CLUE_DISCOVERED,
            investigator_id="inv1",
            location_id="loc1",
            amount=1,
        )
        bus.emit(ctx)

        assert inv.resources == 8
        assert inv.clues == 0
        assert loc.clues == 2  # clue returned to location
        assert ctx.extra["burglary_resources"] is True

    def test_no_effect_when_not_armed(self, setup):
        state, bus, inv, impl, ci = setup
        ctx = EventContext(
            game_state=state,
            event=GameEvent.CLUE_DISCOVERED,
            investigator_id="inv1",
            location_id="loc1",
            amount=1,
        )
        bus.emit(ctx)
        assert inv.resources == 5
