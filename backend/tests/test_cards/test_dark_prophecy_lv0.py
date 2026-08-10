"""Tests for Dark Prophecy (Level 0). (04032)

快速：你将揭示标记时打出（1资源）。改为揭示5个标记，必须选坏符号
（skull/cultist/tablet/elder_thing/auto_fail）结算（自动避开 auto_fail）；
无坏符号时任选（自动取数值最高者）。
"""

import pytest
from backend.cards.mystic.dark_prophecy_lv0 import DarkProphecy
from backend.engine.event_bus import EventBus, EventContext
from backend.models.chaos import ChaosBag
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
        resources=3, hand=["dark_prophecy_lv0"],
    )
    state.investigators["inv1"] = inv
    state.card_database["dark_prophecy_lv0"] = make_event_data(
        id="dark_prophecy_lv0", name="Dark Prophecy", cost=1)
    impl = DarkProphecy("impl_dp")
    impl.register(bus, "impl_dp")
    return state, bus, inv, impl


def _play_and_resolve(state, bus, impl, bag_tokens, seed=0):
    bag = ChaosBag(tokens=list(bag_tokens))
    bag.seed(seed)
    impl.bind_chaos_bag(bag)
    rctx = EventContext(
        game_state=state, event=GameEvent.CHAOS_TOKEN_REVEALED,
        investigator_id="inv1", chaos_token=ChaosTokenType.ZERO,
    )
    bus.emit(rctx)
    ctx = EventContext(
        game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
        investigator_id="inv1", chaos_token=ChaosTokenType.ZERO, amount=0,
    )
    bus.emit(ctx)
    return ctx


class TestDarkProphecy:
    def test_auto_played_on_reveal(self, setup):
        """即将揭示标记时：自动从手牌打出（付1资源）。"""
        state, bus, inv, impl = setup
        ctx = _play_and_resolve(state, bus, impl,
                                [ChaosTokenType.SKULL, ChaosTokenType.ZERO])
        assert inv.resources == 2
        assert "dark_prophecy_lv0" in inv.discard
        assert len(ctx.extra["dark_prophecy_drawn"]) == 5

    def test_must_choose_bad_symbol(self, setup):
        """有坏符号必须结算坏符号（袋中数值标记不可选）。"""
        state, bus, inv, impl = setup
        ctx = _play_and_resolve(
            state, bus, impl,
            [ChaosTokenType.SKULL, ChaosTokenType.PLUS_1])
        assert ctx.chaos_token == ChaosTokenType.SKULL
        assert ctx.amount == 0  # 符号标记修正按0
        assert ctx.extra["cancel_auto_fail"] is True

    def test_avoids_auto_fail_when_other_bad_symbol(self, setup):
        """坏符号中自动避开 auto_fail（seed 0 抽到 skull 与 auto_fail）。"""
        state, bus, inv, impl = setup
        ctx = _play_and_resolve(
            state, bus, impl,
            [ChaosTokenType.AUTO_FAIL, ChaosTokenType.SKULL], seed=0)
        assert set(ctx.extra["dark_prophecy_drawn"]) == {"skull", "auto_fail"}
        assert ctx.chaos_token == ChaosTokenType.SKULL

    def test_forced_auto_fail_when_only_auto_fail(self, setup):
        """5个全是 auto_fail 时只能结算 auto_fail。"""
        state, bus, inv, impl = setup
        ctx = _play_and_resolve(state, bus, impl, [ChaosTokenType.AUTO_FAIL])
        assert ctx.chaos_token == ChaosTokenType.AUTO_FAIL
        assert ctx.extra["force_auto_fail"] is True

    def test_no_bad_symbol_picks_highest(self, setup):
        """无坏符号：任选——自动取数值最高者。"""
        state, bus, inv, impl = setup
        ctx = _play_and_resolve(
            state, bus, impl,
            [ChaosTokenType.MINUS_1, ChaosTokenType.PLUS_1], seed=3)
        drawn = ctx.extra["dark_prophecy_drawn"]
        best = max(drawn, key=lambda v: 1 if v == "+1" else -1)
        assert ctx.extra["dark_prophecy_chosen"] == best

    def test_not_played_without_resources(self, setup):
        state, bus, inv, impl = setup
        inv.resources = 0
        bag = ChaosBag(tokens=[ChaosTokenType.SKULL])
        impl.bind_chaos_bag(bag)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_REVEALED,
            investigator_id="inv1", chaos_token=ChaosTokenType.ZERO,
        ))
        ctx = EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.MINUS_2, amount=-2,
        )
        bus.emit(ctx)
        assert ctx.chaos_token == ChaosTokenType.MINUS_2
        assert "dark_prophecy_lv0" in inv.hand
