"""Tests for Black Market (Level 2)."""

import pytest
from backend.cards.rogue.black_market_lv2 import BlackMarket
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import GameState, InvestigatorState, ScenarioState
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
    inv.deck = [f"card_{i}" for i in range(8)]
    state.investigators["inv1"] = inv

    impl = BlackMarket("bm_inst")
    impl.register(bus, "bm_inst")
    return state, bus, inv, impl


class TestBlackMarket:
    def test_reveal_five_set_aside(self, setup):
        """打出：牌堆顶5张被置于一旁（场外）。"""
        state, bus, inv, impl = setup
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1", extra={"card_id": "black_market_lv2"},
        )
        bus.emit(ctx)
        assert impl._set_aside == [f"card_{i}" for i in range(5)]
        assert inv.deck == ["card_5", "card_6", "card_7"]
        assert state.scenario.vars["black_market_set_aside"]["cards"] == [
            f"card_{i}" for i in range(5)]

    def test_shuffle_back_next_investigation_phase(self, setup):
        """跨轮存活：ROUND_ENDS 自我续注册，下个调查阶段开始洗回并注销。"""
        state, bus, inv, impl = setup
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1", extra={"card_id": "black_market_lv2"},
        ))
        # 跨轮（真实对局中引擎会在 ROUND_ENDS 清理事件实例，本实现随之
        # 自我续注册；总线级测试中重复注册的处理是幂等的）
        bus.emit(EventContext(game_state=state, event=GameEvent.ROUND_ENDS))
        ctx = EventContext(
            game_state=state, event=GameEvent.INVESTIGATION_PHASE_BEGINS,
        )
        bus.emit(ctx)
        assert sorted(inv.deck) == [f"card_{i}" for i in range(8)]
        assert "black_market_set_aside" not in state.scenario.vars
        assert ctx.extra["black_market_returned"] == [f"card_{i}" for i in range(5)]

    def test_partial_deck(self, setup):
        """牌堆不足5张：全部置于一旁。"""
        state, bus, inv, impl = setup
        inv.deck = ["only_a", "only_b"]
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1", extra={"card_id": "black_market_lv2"},
        )
        bus.emit(ctx)
        assert impl._set_aside == ["only_a", "only_b"]
        assert inv.deck == []
