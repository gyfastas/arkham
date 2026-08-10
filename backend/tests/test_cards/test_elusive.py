"""Tests for Elusive (Level 0)."""

import pytest
from backend.cards.rogue.elusive_lv0 import Elusive
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


def _make_state():
    state = GameState(scenario=ScenarioState(scenario_id="test"))

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data

    for lid, conns in (("loc1", ["loc2"]), ("loc2", ["loc1"]), ("loc3", [])):
        loc_data = make_location_data(id=lid, connections=conns)
        state.card_database[lid] = loc_data
        state.locations[lid] = LocationState(
            location_id=lid, card_data=loc_data, revealed=True,
        )

    enemy_data = make_enemy_data(id="ghoul")
    state.card_database["ghoul"] = enemy_data
    enemy = CardInstance(
        instance_id="ghoul_1", card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    state.cards_in_play["ghoul_1"] = enemy

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
    )
    inv.threat_area.append("ghoul_1")
    state.investigators["inv1"] = inv
    return state, inv


@pytest.fixture
def setup():
    state, inv = _make_state()
    bus = EventBus()
    impl = Elusive("elusive_inst")
    impl.register(bus, "elusive_inst")
    return state, bus, inv, impl


def _play(bus, state):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "elusive_lv0"},
    )
    bus.emit(ctx)
    return ctx


class TestElusive:
    def test_card_id(self, setup):
        """Elusive has correct card_id."""
        assert Elusive.card_id == "elusive_lv0"

    def test_disengage_and_move_to_connected(self, setup):
        """Disengage from all enemies and move to a revealed enemy-free connection."""
        state, bus, inv, impl = setup
        ctx = _play(bus, state)

        assert inv.threat_area == []
        assert "ghoul_1" in state.locations["loc1"].enemies
        assert inv.location_id == "loc2"
        assert ctx.extra["elusive_moved_to"] == "loc2"

    def test_skips_unrevealed_connection(self, setup):
        """Unrevealed locations are not valid destinations."""
        state, bus, inv, impl = setup
        state.locations["loc2"].revealed = False

        ctx = _play(bus, state)
        # loc2 unrevealed → fallback to any revealed enemy-free location (loc3)
        assert inv.location_id == "loc3"

    def test_fallback_to_any_revealed_location(self, setup):
        """Falls back to a non-connected revealed location with no enemies."""
        state, bus, inv, impl = setup
        # loc2 has an enemy
        state.locations["loc2"].enemies.append("ghoul_2")

        ctx = _play(bus, state)
        assert inv.location_id == "loc3"

    def test_no_move_when_no_valid_destination(self, setup):
        """No movement when every revealed location has enemies."""
        state, bus, inv, impl = setup
        state.locations["loc2"].enemies.append("ghoul_2")
        state.locations["loc3"].enemies.append("ghoul_3")

        ctx = _play(bus, state)
        assert inv.location_id == "loc1"
        assert "elusive_moved_to" not in ctx.extra
