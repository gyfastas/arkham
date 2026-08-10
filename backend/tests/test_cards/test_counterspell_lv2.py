"""Tests for Counterspell (Level 2). (04110)

快速：你所在地点的检定揭示 skull/cultist/tablet/elder_thing 时自动从手牌
打出（2资源），取消该标记（修正清零、符号效果被抑制、不重抽）。
"""

import pytest
from backend.cards.mystic.counterspell_lv2 import Counterspell
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
        resources=5, hand=["counterspell_lv2"],
    )
    state.investigators["inv1"] = inv
    state.card_database["counterspell_lv2"] = make_event_data(
        id="counterspell_lv2", name="Counterspell", cost=2)
    impl = Counterspell("impl_cs")
    impl.register(bus, "impl_cs")
    return state, bus, inv, impl


def _token_ctx(state, token, amount):
    return EventContext(
        game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
        investigator_id="inv1", chaos_token=token, amount=amount,
    )


class TestCounterspell:
    def test_cancels_skull_token(self, setup):
        """ skull 标记：付2资源取消，修正清零、符号被抑制。"""
        state, bus, inv, impl = setup
        ctx = _token_ctx(state, ChaosTokenType.SKULL, -1)
        bus.emit(ctx)
        assert inv.resources == 3
        assert "counterspell_lv2" not in inv.hand
        assert "counterspell_lv2" in inv.discard
        assert ctx.amount == 0
        assert ctx.chaos_token is None
        assert ctx.extra["counterspell_cancelled"] == "skull"

    def test_ignores_numbered_tokens(self, setup):
        """数值标记不触发。"""
        state, bus, inv, impl = setup
        ctx = _token_ctx(state, ChaosTokenType.MINUS_2, -2)
        bus.emit(ctx)
        assert ctx.amount == -2
        assert inv.resources == 5
        assert "counterspell_lv2" in inv.hand

    def test_ignores_auto_fail(self, setup):
        """auto_fail 不在卡面列表中，不触发。"""
        state, bus, inv, impl = setup
        ctx = _token_ctx(state, ChaosTokenType.AUTO_FAIL, 0)
        bus.emit(ctx)
        assert ctx.chaos_token == ChaosTokenType.AUTO_FAIL
        assert "counterspell_lv2" in inv.hand

    def test_not_played_without_resources(self, setup):
        state, bus, inv, impl = setup
        inv.resources = 1
        ctx = _token_ctx(state, ChaosTokenType.CULTIST, -2)
        bus.emit(ctx)
        assert ctx.amount == -2
        assert "counterspell_lv2" in inv.hand

    def test_not_triggered_from_other_location_holder_only(self, setup):
        """持有者与检定者不同地点时不触发。"""
        state, bus, inv, impl = setup
        # 检定者 inv2 在 loc1；持有者 inv1 在 loc2
        inv.location_id = "loc2"
        tester_data = make_investigator_data(id="inv2_data")
        state.card_database["inv2_data"] = tester_data
        state.investigators["inv2"] = InvestigatorState(
            investigator_id="inv2", card_data=tester_data, location_id="loc1",
        )
        ctx = EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv2", chaos_token=ChaosTokenType.SKULL, amount=-1,
        )
        bus.emit(ctx)
        assert ctx.amount == -1
        assert "counterspell_lv2" in inv.hand
