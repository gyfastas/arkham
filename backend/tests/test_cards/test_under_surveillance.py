"""Tests for Under Surveillance (Level 1)."""

import pytest

from backend.cards.rogue.under_surveillance_lv1 import UnderSurveillance
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
    loc_data = make_location_data(id="loc1")
    state.card_database["loc1"] = loc_data
    state.locations["loc1"] = LocationState(
        location_id="loc1", card_data=loc_data, clues=2)
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    state.investigators["inv1"] = inv
    thug = make_enemy_data(id="thug")
    state.card_database["thug"] = thug
    boss = make_enemy_data(id="boss", keywords=["elite"])
    state.card_database["boss"] = boss
    impl = UnderSurveillance("us_inst")
    impl.register(bus, "us_inst")
    return state, bus, inv, impl


def _play(bus, state):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "under_surveillance_lv1"},
    )
    bus.emit(ctx)
    return ctx


def _enemy_enters(bus, state, iid, card_id):
    state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id=card_id,
        owner_id="scenario", controller_id="scenario")
    inv = state.get_investigator("inv1")
    inv.threat_area.append(iid)
    ctx = EventContext(
        game_state=state,
        event=GameEvent.ENEMY_ENGAGED,
        investigator_id="inv1",
        enemy_id=iid,
    )
    bus.emit(ctx)
    return ctx


class TestUnderSurveillance:
    def test_attach_on_play(self, setup):
        state, bus, inv, impl = setup
        ctx = _play(bus, state)
        assert ctx.extra["under_surveillance_location"] == "loc1"

    def test_non_elite_enemy_triggers_trap(self, setup):
        state, bus, inv, impl = setup
        _play(bus, state)
        ctx = _enemy_enters(bus, state, "enemy_1", "thug")
        enemy = state.get_card_instance("enemy_1")
        assert ctx.extra["under_surveillance_evaded"] == "enemy_1"
        assert enemy.exhausted is True
        assert "enemy_1" not in inv.threat_area
        assert "enemy_1" in state.locations["loc1"].enemies
        # 发现1个线索
        assert state.locations["loc1"].clues == 1
        assert inv.clues == 1
        # 标记已消耗（一次性陷阱）
        assert state.scenario.vars["under_surveillance_locations"] == {}

    def test_enemy_skips_next_upkeep_ready(self, setup):
        state, bus, inv, impl = setup
        _play(bus, state)
        _enemy_enters(bus, state, "enemy_1", "thug")
        enemy = state.get_card_instance("enemy_1")
        # 补给阶段引擎将就绪它并发出 CARD_READIED
        enemy.exhausted = False
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_READIED, target="enemy_1"))
        assert enemy.exhausted is True

    def test_elite_enemy_ignored(self, setup):
        state, bus, inv, impl = setup
        _play(bus, state)
        ctx = _enemy_enters(bus, state, "enemy_2", "boss")
        assert "under_surveillance_evaded" not in ctx.extra
        assert "enemy_2" in inv.threat_area
        # 陷阱未被消耗
        assert state.scenario.vars["under_surveillance_locations"]

    def test_enemy_at_other_location_ignored(self, setup):
        state, bus, inv, impl = setup
        _play(bus, state)
        inv.location_id = "elsewhere"
        ctx = _enemy_enters(bus, state, "enemy_1", "thug")
        assert "under_surveillance_evaded" not in ctx.extra
