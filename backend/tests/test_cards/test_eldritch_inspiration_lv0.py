"""Tests for Eldritch Inspiration (Level 0). (05033)

快速（0费）：你的检定揭示 skull/cultist/tablet/elder_thing/auto_fail 时
自动从手牌打出；模式（cancel/double）写入 scenario.vars 供 mystic 卡的
符号触发效果查询（通用取消/重放为引擎缺口）。
"""

import pytest
from backend.cards.mystic.eldritch_inspiration_lv0 import EldritchInspiration
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_event_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        resources=0, hand=["eldritch_inspiration_lv0"],
    )
    state.investigators["inv1"] = inv
    state.card_database["eldritch_inspiration_lv0"] = make_event_data(
        id="eldritch_inspiration_lv0", name="Eldritch Inspiration", cost=0)
    impl = EldritchInspiration("impl_ei")
    impl.register(bus, "impl_ei")
    return state, bus, inv, impl


def _token(state, bus, token):
    ctx = EventContext(
        game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
        investigator_id="inv1", chaos_token=token, amount=-1,
    )
    bus.emit(ctx)
    return ctx


class TestEldritchInspiration:
    def test_auto_play_on_symbol_default_double(self, setup):
        """揭示 skull：自动打出（0费），默认模式 double 写入 vars。"""
        state, bus, inv, impl = setup
        ctx = _token(state, bus, ChaosTokenType.SKULL)
        assert "eldritch_inspiration_lv0" in inv.discard
        assert inv.hand == []
        assert ctx.extra["eldritch_inspiration_played"] == "double"
        entry = state.scenario.vars["eldritch_inspiration"]
        assert entry["mode"] == "double"
        assert entry["token"] == "skull"

    def test_cancel_mode_preset(self, setup):
        """会话层预设 cancel 模式。"""
        state, bus, inv, impl = setup
        impl.pending_mode = "cancel"
        ctx = _token(state, bus, ChaosTokenType.AUTO_FAIL)
        assert ctx.extra["eldritch_inspiration_played"] == "cancel"
        assert state.scenario.vars["eldritch_inspiration"]["mode"] == "cancel"

    def test_consume_mode_one_shot(self, setup):
        """consume_mode 消费后清除。"""
        state, bus, inv, impl = setup
        _token(state, bus, ChaosTokenType.CULTIST)
        assert EldritchInspiration.consume_mode(state, "inv1") == "double"
        assert EldritchInspiration.consume_mode(state, "inv1") is None

    def test_not_triggered_on_numbered_token(self, setup):
        state, bus, inv, impl = setup
        _token(state, bus, ChaosTokenType.MINUS_2)
        assert "eldritch_inspiration_lv0" in inv.hand
        assert "eldritch_inspiration" not in state.scenario.vars
