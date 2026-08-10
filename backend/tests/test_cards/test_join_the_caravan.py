"""Tests for Join the Caravan (Level 1)."""

import pytest
from backend.cards.seeker.join_the_caravan_lv1 import JoinTheCaravan
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, PlayerClass
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    for loc_id, revealed in [("loc_a", True), ("loc_b", True), ("loc_c", False)]:
        loc_data = make_location_data(id=loc_id)
        state.card_database[loc_id] = loc_data
        state.locations[loc_id] = LocationState(
            location_id=loc_id, card_data=loc_data, revealed=revealed,
        )
    # 场上两张开卡：guardian + seeker（两种职阶）
    g_data = make_asset_data(id="g_asset", card_class=PlayerClass.GUARDIAN)
    s_data = make_asset_data(id="s_asset", card_class=PlayerClass.SEEKER)
    state.card_database["g_asset"] = g_data
    state.card_database["s_asset"] = s_data

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data,
        location_id="loc_a", resources=0,
    )
    state.investigators["inv1"] = inv
    for iid, cid in [("i1", "g_asset"), ("i2", "s_asset")]:
        state.cards_in_play[iid] = CardInstance(
            instance_id=iid, card_id=cid, owner_id="inv1", controller_id="inv1",
        )
        inv.play_area.append(iid)

    impl = JoinTheCaravan("jtc_1")
    impl.register(bus, "jtc_1")
    return state, bus, inv, impl


def _play(state, bus, **extra):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "join_the_caravan_lv1", **extra},
    )
    bus.emit(ctx)
    return ctx


class TestJoinTheCaravan:
    def test_refund_per_distinct_class(self, setup):
        """你控制卡牌的不同职阶数=2 → 返还2资源（净支出3）。"""
        state, bus, inv, impl = setup
        ctx = _play(state, bus)
        assert ctx.extra["join_the_caravan_refund"] == 2
        assert inv.resources == 2

    def test_move_to_first_revealed_location(self, setup):
        """默认移动到第一个非当前地点的已揭示地点。"""
        state, bus, inv, impl = setup
        ctx = _play(state, bus)
        assert ctx.extra["join_the_caravan_moved_to"] == "loc_b"
        assert inv.location_id == "loc_b"

    def test_explicit_destination(self, setup):
        """显式目的地；未揭示地点不可选。"""
        state, bus, inv, impl = setup
        ctx = _play(state, bus, destination="loc_c")
        assert "join_the_caravan_moved_to" not in ctx.extra
        assert inv.location_id == "loc_a"
