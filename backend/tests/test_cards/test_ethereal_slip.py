"""Tests for Ethereal Slip (Level 0 / Level 2)."""

import pytest
from backend.cards.rogue.ethereal_slip_lv0 import EtherealSlip
from backend.cards.rogue.ethereal_slip_lv2 import EtherealSlipLv2
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


def _build_state():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data

    loc_a = make_location_data(id="loc_a", connections=["loc_b"])
    loc_b = make_location_data(id="loc_b", connections=["loc_a", "loc_c"])
    loc_c = make_location_data(id="loc_c", connections=["loc_b"])
    loc_far = make_location_data(id="loc_far", connections=[])
    for ld in (loc_a, loc_b, loc_c, loc_far):
        state.card_database[ld.id] = ld
        state.locations[ld.id] = LocationState(
            location_id=ld.id, card_data=ld, revealed=True,
        )

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc_a",
    )
    state.investigators["inv1"] = inv

    state.card_database["mook"] = make_enemy_data(id="mook")
    state.card_database["boss"] = make_enemy_data(id="boss", keywords=["elite"])
    return state, bus, inv


def _add_enemy(state, card_id, instance_id, loc_id):
    state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    state.locations[loc_id].enemies.append(instance_id)


class TestEtherealSlipLv0:
    @pytest.fixture
    def setup(self):
        state, bus, inv = _build_state()
        impl = EtherealSlip("es_inst")
        impl.register(bus, "es_inst")
        return state, bus, inv, impl

    def _play(self, bus, state, extra=None):
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "ethereal_slip_lv0", **(extra or {})},
        )
        bus.emit(ctx)
        return ctx

    def test_swap_with_enemy_two_connections_away(self, setup):
        """与2连接外的非精英敌人交换位置。"""
        state, bus, inv, impl = setup
        _add_enemy(state, "mook", "e1", "loc_c")
        ctx = self._play(bus, state)
        assert inv.location_id == "loc_c"
        assert "e1" in state.locations["loc_a"].enemies
        assert "e1" not in state.locations["loc_c"].enemies
        assert ctx.extra["ethereal_slip_swapped"] == "e1"
        assert ctx.extra["ethereal_slip_moved_to"] == "loc_c"

    def test_elite_skipped_for_next_valid(self, setup):
        """精英敌人被跳过，自动选择下一个合法目标。"""
        state, bus, inv, impl = setup
        _add_enemy(state, "boss", "e1", "loc_b")
        _add_enemy(state, "mook", "e2", "loc_c")
        ctx = self._play(bus, state)
        assert ctx.extra["ethereal_slip_swapped"] == "e2"
        assert inv.location_id == "loc_c"

    def test_out_of_range_not_targeted(self, setup):
        """距离超过2的地点不是合法目标（自动选择不到）。"""
        state, bus, inv, impl = setup
        _add_enemy(state, "mook", "e1", "loc_far")  # 无连接，不可达
        ctx = self._play(bus, state)
        assert "ethereal_slip_swapped" not in ctx.extra
        assert inv.location_id == "loc_a"

    def test_explicit_target_out_of_range_rejected(self, setup):
        state, bus, inv, impl = setup
        _add_enemy(state, "mook", "e1", "loc_far")
        ctx = self._play(bus, state, extra={"target_enemy_id": "e1"})
        assert "ethereal_slip_swapped" not in ctx.extra


class TestEtherealSlipLv2:
    @pytest.fixture
    def setup(self):
        state, bus, inv = _build_state()
        impl = EtherealSlipLv2("es2_inst")
        impl.register(bus, "es2_inst")
        return state, bus, inv, impl

    def test_swap_with_any_revealed_location(self, setup):
        """lv2：任意已揭示地点（无连接也可）。"""
        state, bus, inv, impl = setup
        _add_enemy(state, "mook", "e1", "loc_far")
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "ethereal_slip_lv2"},
        )
        bus.emit(ctx)
        assert inv.location_id == "loc_far"
        assert "e1" in state.locations["loc_a"].enemies
        assert ctx.extra["ethereal_slip_swapped"] == "e1"
