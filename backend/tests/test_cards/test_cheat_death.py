"""Tests for Cheat Death (Level 5)."""

import pytest
from backend.cards.rogue.cheat_death_lv5 import CheatDeath
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import CardType, GameEvent
from backend.models.state import (
    CardData, CardInstance, GameState, InvestigatorState, LocationState,
    ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(health=7, sanity=7)
    state.card_database[inv_data.id] = inv_data
    state.card_database["cheat_death_lv5"] = make_event_data(
        id="cheat_death_lv5", cost=1, fast=True,
    )
    state.card_database["ghoul"] = make_enemy_data(id="ghoul")
    state.card_database["whispers"] = CardData(
        id="whispers", name="Whispers", name_cn="低语",
        type=CardType.TREACHERY,
    )

    loc_data = make_location_data(id="loc1")
    state.card_database["loc1"] = loc_data
    state.locations["loc1"] = LocationState(
        location_id="loc1", card_data=loc_data, revealed=True,
    )
    safe_data = make_location_data(id="loc2")
    state.card_database["loc2"] = safe_data
    state.locations["loc2"] = LocationState(
        location_id="loc2", card_data=safe_data, revealed=True,
    )

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        hand=["cheat_death_lv5"], resources=3,
        damage=5, horror=5, actions_remaining=2,
    )
    state.investigators["inv1"] = inv

    # Engaged enemy + a treachery in the threat area
    state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    state.cards_in_play["treach_1"] = CardInstance(
        instance_id="treach_1", card_id="whispers",
        owner_id="inv1", controller_id="inv1",
    )
    inv.threat_area.extend(["enemy_1", "treach_1"])

    impl = CheatDeath("cd_inst")
    impl.register(bus, "cd_inst")
    return state, bus, inv, impl


def _defeated(bus, state, **extra):
    ctx = EventContext(
        game_state=state, event=GameEvent.INVESTIGATOR_DEFEATED,
        investigator_id="inv1", extra=dict(extra),
    )
    bus.emit(ctx)
    return ctx


class TestCheatDeath:
    def test_card_id(self):
        assert CheatDeath.card_id == "cheat_death_lv5"

    def test_full_effect_on_defeat(self, setup):
        """Would be defeated: heal 2/2, disengage, clear threat area, move."""
        state, bus, inv, impl = setup
        ctx = _defeated(bus, state)

        assert ctx.extra["cheat_death_saved"] is True
        # Cost paid; removed from game (not in discard)
        assert inv.resources == 2
        assert "cheat_death_lv5" not in inv.hand
        assert "cheat_death_lv5" not in inv.discard
        # Heal 2 damage + 2 horror
        assert inv.damage == 3
        assert inv.horror == 3
        # Disengaged: enemy back at current location
        assert "enemy_1" not in inv.threat_area
        assert "enemy_1" in state.locations["loc1"].enemies
        assert "enemy_1" in state.cards_in_play  # enemy not discarded
        # Threat-area treachery discarded
        assert "treach_1" not in inv.threat_area
        assert "treach_1" not in state.cards_in_play
        assert "whispers" in inv.discard
        # Moved to revealed location with no enemies
        assert inv.location_id == "loc2"
        assert ctx.extra["cheat_death_moved_to"] == "loc2"
        # Turn ended
        assert inv.actions_remaining == 0

    def test_explicit_destination(self, setup):
        state, bus, inv, impl = setup
        ctx = _defeated(bus, state, destination="loc2")
        assert inv.location_id == "loc2"

    def test_no_trigger_without_card_in_hand(self, setup):
        state, bus, inv, impl = setup
        inv.hand.remove("cheat_death_lv5")
        ctx = _defeated(bus, state)
        assert inv.damage == 5
        assert "cheat_death_saved" not in ctx.extra

    def test_no_trigger_without_resources(self, setup):
        state, bus, inv, impl = setup
        inv.resources = 0
        ctx = _defeated(bus, state)
        assert inv.damage == 5
        assert "cheat_death_saved" not in ctx.extra
