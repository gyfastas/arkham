"""Tests for Extensive Research (Level 1)."""

import pytest
from backend.cards.seeker.extensive_research_lv1 import ExtensiveResearch
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    GameState, InvestigatorState, LocationState, ScenarioState,
)
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
        investigator_id="inv1", card_data=inv_data,
        location_id="test_location",
        hand=["c1", "c2", "c3", "c4"], resources=10,
    )
    state.investigators["inv1"] = inv
    loc = LocationState(location_id="test_location", card_data=loc_data, clues=3)
    state.locations["test_location"] = loc

    impl = ExtensiveResearch("er_1")
    impl.register(bus, "er_1")
    return state, bus, inv, loc, impl


def _play(state, bus, hand=None):
    if hand is not None:
        state.get_investigator("inv1").hand = hand
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "extensive_research_lv1"},
    )
    bus.emit(ctx)
    return ctx


class TestExtensiveResearch:
    def test_discover_two_clues(self, setup):
        """发现你所在地点的2个线索。"""
        state, bus, inv, loc, impl = setup
        ctx = _play(state, bus)
        assert ctx.extra["extensive_research_clues"] == 2
        assert loc.clues == 1
        assert inv.clues == 2

    def test_cost_refund_per_other_card_in_hand(self, setup):
        """每张其它手牌返还1资源（净支出 = 10 - 手牌数）。"""
        state, bus, inv, loc, impl = setup
        inv.resources = 6  # 模拟支付全额10点后的剩余（16-10）
        ctx = _play(state, bus)  # 手牌4张（不含本卡）
        assert ctx.extra["extensive_research_refund"] == 4
        assert inv.resources == 10  # 净支出6 = 10 - 4

    def test_refund_scales_with_hand_size(self, setup):
        state, bus, inv, loc, impl = setup
        inv.resources = 0
        ctx = _play(state, bus, hand=["c1"])
        assert ctx.extra["extensive_research_refund"] == 1
        assert inv.resources == 1

    def test_fewer_clues_than_two(self, setup):
        """地点只剩1个线索时只发现1个。"""
        state, bus, inv, loc, impl = setup
        loc.clues = 1
        ctx = _play(state, bus)
        assert ctx.extra["extensive_research_clues"] == 1
        assert inv.clues == 1
        assert loc.clues == 0
