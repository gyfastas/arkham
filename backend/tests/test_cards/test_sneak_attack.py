"""Tests for Sneak Attack (Level 0)."""

import pytest
from backend.cards.rogue.sneak_attack_lv0 import SneakAttack
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data

    card_data = make_event_data(id="sneak_attack_lv0")
    state.card_database["sneak_attack_lv0"] = card_data

    enemy_data = make_enemy_data(id="ghoul")
    state.card_database["ghoul"] = enemy_data

    loc_data = make_location_data(id="loc1")
    state.card_database["loc1"] = loc_data
    loc = LocationState(location_id="loc1", card_data=loc_data, revealed=True)
    state.locations["loc1"] = loc

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
    )
    state.investigators["inv1"] = inv

    enemy_inst = CardInstance(
        instance_id="ghoul_1",
        card_id="ghoul",
        owner_id="scenario",
        controller_id="scenario",
        exhausted=True,
    )
    enemy_inst.damage = 0
    state.cards_in_play["ghoul_1"] = enemy_inst
    loc.enemies.append("ghoul_1")

    impl = SneakAttack("sneak_inst")
    impl.register(bus, "sneak_inst")
    return state, bus, inv, impl


def _play(bus, state, **extra):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "sneak_attack_lv0", **extra},
    )
    bus.emit(ctx)
    return ctx


class TestSneakAttack:
    def test_deal_damage_to_exhausted_enemy(self, setup):
        """Sneak Attack deals 2 damage to an exhausted enemy at your location."""
        state, bus, inv, impl = setup

        ctx = _play(bus, state, target_enemy_id="ghoul_1")

        assert state.cards_in_play["ghoul_1"].damage == 2
        assert ctx.extra["sneak_attack_target"] == "ghoul_1"

    def test_auto_selects_exhausted_enemy(self, setup):
        """Without an explicit target, the first exhausted enemy at your location is chosen."""
        state, bus, inv, impl = setup

        ctx = _play(bus, state)

        assert state.cards_in_play["ghoul_1"].damage == 2
        assert ctx.extra["sneak_attack_target"] == "ghoul_1"

    def test_no_damage_to_ready_enemy(self, setup):
        """A non-exhausted enemy is not a valid target."""
        state, bus, inv, impl = setup
        state.cards_in_play["ghoul_1"].exhausted = False

        _play(bus, state, target_enemy_id="ghoul_1")

        assert state.cards_in_play["ghoul_1"].damage == 0

    def test_no_damage_to_enemy_elsewhere(self, setup):
        """An exhausted enemy at another location is not a valid target."""
        state, bus, inv, impl = setup
        state.locations["loc1"].enemies.remove("ghoul_1")

        _play(bus, state, target_enemy_id="ghoul_1")

        assert state.cards_in_play["ghoul_1"].damage == 0
