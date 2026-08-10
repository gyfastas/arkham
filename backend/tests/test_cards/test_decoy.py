"""Tests for Decoy (Level 0)."""

import pytest
from backend.cards.rogue.decoy_lv0 import Decoy
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

    loc_a = make_location_data(id="loc_a", connections=["loc_b"])
    loc_b = make_location_data(id="loc_b", connections=["loc_a", "loc_c"])
    loc_c = make_location_data(id="loc_c", connections=["loc_b"])
    for ld in (loc_a, loc_b, loc_c):
        state.card_database[ld.id] = ld
        state.locations[ld.id] = LocationState(
            location_id=ld.id, card_data=ld, revealed=True,
        )

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc_a",
    )
    inv.resources = 5
    state.investigators["inv1"] = inv

    state.card_database["mook"] = make_enemy_data(id="mook", health=5)
    state.card_database["boss"] = make_enemy_data(
        id="boss", health=5, keywords=["elite"])

    impl = Decoy("decoy_inst")
    impl.register(bus, "decoy_inst")
    return state, bus, inv, impl


def _add_enemy(state, card_id, instance_id, loc_id):
    state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    state.locations[loc_id].enemies.append(instance_id)


def _play(bus, state, extra=None):
    ctx = EventContext(
        game_state=state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "decoy_lv0", **(extra or {})},
    )
    bus.emit(ctx)
    return ctx


class TestDecoy:
    def test_auto_evade_non_elite_at_your_location(self, setup):
        """自动躲避你所在地点的非精英敌人（横置、解除交战、发事件）。"""
        state, bus, inv, impl = setup
        _add_enemy(state, "mook", "e1", "loc_a")
        inv.threat_area.append("e1")
        state.locations["loc_a"].enemies.remove("e1")
        evaded = []
        bus.register(
            event=GameEvent.ENEMY_EVADED,
            handler=lambda c: evaded.append(c.enemy_id),
        )
        ctx = _play(bus, state)
        enemy = state.get_card_instance("e1")
        assert enemy.exhausted is True
        assert "e1" not in inv.threat_area
        assert "e1" in state.locations["loc_a"].enemies
        assert evaded == ["e1"]
        assert ctx.extra["decoy_evaded"] == ["e1"]

    def test_elite_not_targeted(self, setup):
        """精英敌人不是合法目标（无其他敌人时无效果）。"""
        state, bus, inv, impl = setup
        _add_enemy(state, "boss", "e1", "loc_a")
        ctx = _play(bus, state)
        assert state.get_card_instance("e1").exhausted is False
        assert "decoy_evaded" not in ctx.extra

    def test_base_effect_cannot_reach_other_locations(self, setup):
        """基础效果仅限你所在地点。"""
        state, bus, inv, impl = setup
        _add_enemy(state, "mook", "e1", "loc_b")
        ctx = _play(bus, state)
        assert state.get_card_instance("e1").exhausted is False
        assert "decoy_evaded" not in ctx.extra

    def test_boost_range_reaches_two_connections(self, setup):
        """升级距离（+2费）：可及2连接外的地点。"""
        state, bus, inv, impl = setup
        _add_enemy(state, "mook", "e1", "loc_c")
        ctx = _play(bus, state, extra={"decoy_boost_range": True})
        assert inv.resources == 3  # 5-2 升级补扣
        assert state.get_card_instance("e1").exhausted is True
        assert ctx.extra["decoy_evaded"] == ["e1"]

    def test_boost_targets_evades_two(self, setup):
        """升级数量（+2费）：最多躲避2名非精英敌人。"""
        state, bus, inv, impl = setup
        _add_enemy(state, "mook", "e1", "loc_a")
        _add_enemy(state, "mook", "e2", "loc_a")
        _add_enemy(state, "mook", "e3", "loc_a")
        ctx = _play(bus, state, extra={"decoy_boost_targets": True})
        assert inv.resources == 3
        assert len(ctx.extra["decoy_evaded"]) == 2
        assert state.get_card_instance("e3").exhausted is False
