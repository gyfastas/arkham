"""Tests for Small Favor (Level 0)."""

import pytest

from backend.cards.rogue.small_favor_lv0 import SmallFavor
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    # loc1 - loc2 - loc3
    conns = {"loc1": ["loc2"], "loc2": ["loc1", "loc3"], "loc3": ["loc2"]}
    for loc_id, links in conns.items():
        ld = make_location_data(id=loc_id, connections=links)
        state.card_database[loc_id] = ld
        state.locations[loc_id] = LocationState(location_id=loc_id, card_data=ld)
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    inv.resources = 5
    state.investigators["inv1"] = inv

    thug = make_enemy_data(id="thug", health=2)
    state.card_database["thug"] = thug
    elite = make_enemy_data(id="boss", health=2, keywords=["elite"])
    state.card_database["boss"] = elite

    impl = SmallFavor("favor_inst")
    impl.register(bus, "favor_inst")
    return state, bus, inv


def _add_enemy(state, iid, card_id, loc_id):
    state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id=card_id,
        owner_id="scenario", controller_id="scenario")
    state.locations[loc_id].enemies.append(iid)


def _play(bus, state, **extra):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "small_favor_lv0", **extra},
    )
    bus.emit(ctx)
    return ctx


class TestSmallFavor:
    def test_auto_boost_damage_defeats_local_enemy(self, setup):
        """Local target + 5 resources: auto +2 cost for 2 damage, defeating 2-health thug."""
        state, bus, inv = setup
        _add_enemy(state, "enemy_1", "thug", "loc1")
        ctx = _play(bus, state)
        assert ctx.extra["small_favor_boost_damage"] is True
        assert ctx.extra["small_favor_damage"] == 2
        assert inv.resources == 3  # 5 - 2 boost
        assert ctx.extra["small_favor_defeated"] == "enemy_1"
        assert "enemy_1" not in state.cards_in_play
        assert "thug" in state.scenario.encounter_discard

    def test_no_boost_when_poor(self, setup):
        state, bus, inv = setup
        inv.resources = 1
        _add_enemy(state, "enemy_1", "thug", "loc1")
        ctx = _play(bus, state)
        assert ctx.extra["small_favor_damage"] == 1
        assert inv.resources == 1
        assert state.get_card_instance("enemy_1").damage == 1

    def test_elite_not_targeted(self, setup):
        state, bus, inv = setup
        _add_enemy(state, "enemy_1", "boss", "loc1")
        ctx = _play(bus, state)
        assert "small_favor_target" not in ctx.extra
        assert state.get_card_instance("enemy_1").damage == 0

    def test_range_boost_reaches_two_hops(self, setup):
        """No local enemy: auto +2 cost to reach an enemy 2 connections away."""
        state, bus, inv = setup
        _add_enemy(state, "enemy_far", "thug", "loc3")
        ctx = _play(bus, state)
        assert ctx.extra.get("small_favor_boost_range") is True
        assert ctx.extra["small_favor_target"] == "enemy_far"
        assert inv.resources == 3
        # 未买伤害增幅：1点伤害
        assert state.get_card_instance("enemy_far").damage == 1

    def test_no_target_no_effect(self, setup):
        state, bus, inv = setup
        ctx = _play(bus, state)
        assert "small_favor_target" not in ctx.extra
        assert inv.resources == 5
