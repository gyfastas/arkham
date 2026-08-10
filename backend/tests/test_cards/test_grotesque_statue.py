"""Tests for Grotesque Statue (Level 4). (01071)

使用(4充能)，无充能时弃置。揭示标记时花1充能：改为揭示2枚，选1枚结算
（简化：自动取对玩家较有利者）。
"""

import pytest
from backend.cards.mystic.grotesque_statue_lv4 import GrotesqueStatue
from backend.engine.event_bus import EventBus, EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv

    state.card_database["grotesque_statue_lv4"] = make_asset_data(
        id="grotesque_statue_lv4", name="Grotesque Statue",
        traits=["item", "relic"], uses={"charges": 4},
    )
    inst = CardInstance(
        instance_id="inst_gs", card_id="grotesque_statue_lv4",
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"charges": 4}
    state.cards_in_play["inst_gs"] = inst
    inv.play_area.append("inst_gs")

    impl = GrotesqueStatue("inst_gs")
    impl.register(bus, "inst_gs")
    return state, bus, inv, inst, impl


def _resolve(state, bus, token, amount):
    ctx = EventContext(
        game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
        investigator_id="inv1", chaos_token=token, amount=amount,
    )
    bus.emit(ctx)
    return ctx


class TestGrotesqueStatue:
    def test_use_spends_charge_and_arms(self, setup):
        state, bus, inv, inst, impl = setup
        assert impl.use(state, "inv1") is True
        assert inst.uses["charges"] == 3

    def test_redraw_draws_two_from_bag_and_picks_favorable(self, setup):
        """从游戏混沌袋连抽2枚，取对玩家较有利者。"""
        state, bus, inv, inst, impl = setup
        bag = ChaosBag(tokens=[ChaosTokenType.MINUS_3, ChaosTokenType.PLUS_1])
        bag.seed(7)  # 确定性抽取序列：+1, -3（非破坏性有放回抽取）
        impl.bind_chaos_bag(bag)
        impl.use(state, "inv1")
        ctx = _resolve(state, bus, ChaosTokenType.MINUS_2, -2)
        assert sorted(ctx.extra["grotesque_statue_drawn"]) == sorted(["-3", "+1"])
        assert ctx.chaos_token == ChaosTokenType.PLUS_1
        assert ctx.amount == 1

    def test_redraw_auto_fail_worst(self, setup):
        """auto_fail 视为最差；两枚都差时仍取较有利者。"""
        state, bus, inv, inst, impl = setup
        bag = ChaosBag(tokens=[ChaosTokenType.AUTO_FAIL, ChaosTokenType.MINUS_1])
        bag.seed(7)  # 确定性：先抽 -1 再抽 auto_fail，取较有利者
        impl.bind_chaos_bag(bag)
        impl.use(state, "inv1")
        ctx = _resolve(state, bus, ChaosTokenType.SKULL, 0)
        assert ctx.chaos_token == ChaosTokenType.MINUS_1
        assert ctx.amount == -1

    def test_redraw_into_auto_fail_forces_failure(self, setup):
        state, bus, inv, inst, impl = setup
        bag = ChaosBag(tokens=[ChaosTokenType.AUTO_FAIL, ChaosTokenType.AUTO_FAIL])
        impl.bind_chaos_bag(bag)
        impl.use(state, "inv1")
        ctx = _resolve(state, bus, ChaosTokenType.ZERO, 0)
        assert ctx.chaos_token == ChaosTokenType.AUTO_FAIL
        assert ctx.extra["force_auto_fail"] is True

    def test_not_armed_no_redraw(self, setup):
        state, bus, inv, inst, impl = setup
        bag = ChaosBag(tokens=[ChaosTokenType.PLUS_1, ChaosTokenType.PLUS_1])
        impl.bind_chaos_bag(bag)
        ctx = _resolve(state, bus, ChaosTokenType.MINUS_2, -2)
        assert ctx.chaos_token == ChaosTokenType.MINUS_2
        assert ctx.amount == -2

    def test_discards_when_charges_run_out(self, setup):
        """花掉最后1充能并完成重抽后：弃置。"""
        state, bus, inv, inst, impl = setup
        inst.uses["charges"] = 1
        bag = ChaosBag(tokens=[ChaosTokenType.ZERO, ChaosTokenType.ZERO])
        impl.bind_chaos_bag(bag)
        assert impl.use(state, "inv1") is True
        _resolve(state, bus, ChaosTokenType.MINUS_1, -1)
        assert "inst_gs" not in inv.play_area
        assert "inst_gs" not in state.cards_in_play
        assert "grotesque_statue_lv4" in inv.discard

    def test_discard_at_test_end_if_empty_without_redraw(self, setup):
        """花掉最后1充能但检定未触发重抽（如检定被取消）：仍在检定结束时弃置。"""
        state, bus, inv, inst, impl = setup
        inst.uses["charges"] = 1
        assert impl.use(state, "inv1") is True
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1",
        ))
        assert "inst_gs" not in inv.play_area
