"""Tests for Double, Double (Level 4)."""

import pytest
from backend.cards.neutral.emergency_cache_lv0 import EmergencyCache
from backend.cards.rogue.double_double_lv4 import DoubleDouble
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    CardData, CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.models.enums import CardType, PlayerClass
from backend.tests.conftest import make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    inv.resources = 10
    state.investigators["inv1"] = inv

    state.card_database["emergency_cache_lv0"] = CardData(
        id="emergency_cache_lv0", name="Emergency Cache", name_cn="应急储备",
        type=CardType.EVENT, card_class=PlayerClass.NEUTRAL, cost=1,
    )
    state.card_database["dummy_event"] = CardData(
        id="dummy_event", name="Dummy", name_cn="假事件",
        type=CardType.EVENT, card_class=PlayerClass.ROGUE, cost=4,
    )

    dd = DoubleDouble("dd_inst")
    dd.register(bus, "dd_inst")
    ci = CardInstance(
        instance_id="dd_inst", card_id="double_double_lv4",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["dd_inst"] = ci
    inv.play_area.append("dd_inst")

    cache = EmergencyCache("cache_temp")
    cache.register(bus, "cache_temp")
    return state, bus, inv, dd, ci


class TestDoubleDouble:
    def test_event_resolves_twice(self, setup):
        """打出事件后消耗本卡：重付费用并再结算一次（应急储备 +3×2）。"""
        state, bus, inv, dd, ci = setup
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "emergency_cache_lv0"},
        )
        bus.emit(ctx)
        assert inv.resources == 10 - 1 + 3 + 3  # 重付1费，效果结算两次
        assert ci.exhausted is True
        assert ctx.extra["double_double_replayed"] == "emergency_cache_lv0"

    def test_no_replay_when_exhausted(self, setup):
        state, bus, inv, dd, ci = setup
        ci.exhausted = True
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "emergency_cache_lv0"},
        )
        bus.emit(ctx)
        assert inv.resources == 13  # 仅结算一次
        assert "double_double_replayed" not in ctx.extra

    def test_no_replay_when_cannot_afford(self, setup):
        """付不起第二次费用：不触发（本卡保持未横置）。"""
        state, bus, inv, dd, ci = setup
        inv.resources = 3  # < dummy_event 费用4
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "dummy_event"},
        )
        bus.emit(ctx)
        assert inv.resources == 3  # 未扣费
        assert ci.exhausted is False
        assert "double_double_replayed" not in ctx.extra
