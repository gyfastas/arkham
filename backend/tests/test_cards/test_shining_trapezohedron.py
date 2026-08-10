"""Tests for Shining Trapezohedron (lv4)."""

import pytest

from backend.cards.mystic.shining_trapezohedron_lv4 import ShiningTrapezohedron
from backend.engine.event_bus import EventBus, EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


def _setup(bag_tokens):
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag(tokens=list(bag_tokens))
    bag.seed(42)

    inv_data = make_investigator_data(willpower=4)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    inv.resources = 5
    state.investigators["inv1"] = inv

    state.card_database["shining_trapezohedron_lv4"] = make_asset_data(
        id="shining_trapezohedron_lv4", cost=1)
    inst = CardInstance(
        instance_id="trap1", card_id="shining_trapezohedron_lv4",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["trap1"] = inst
    inv.play_area.append("trap1")

    # 待打出的法术资产（费用3）
    state.card_database["spell_asset"] = make_asset_data(
        id="spell_asset", cost=3, traits=["spell"])

    impl = ShiningTrapezohedron("trap1")
    impl.register(bus, "trap1")
    impl.bind_chaos_bag(bag)
    return state, bus, bag, inv, inst, impl


def _simulate_asset_play(bus, state, inv, cost=3):
    """模拟 actions._play 的资产打出事件序列：扣费 → RESOURCES_SPENT → 入场。"""
    inv.resources -= cost
    if "spell_asset" in inv.hand:
        inv.hand.remove("spell_asset")
    bus.emit(EventContext(
        game_state=state, event=GameEvent.RESOURCES_SPENT,
        investigator_id="inv1", amount=cost,
    ))
    new_inst = CardInstance(
        instance_id="spell1", card_id="spell_asset",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["spell1"] = new_inst
    inv.play_area.append("spell1")
    ctx = EventContext(
        game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
        investigator_id="inv1", target="spell1",
        extra={"card_id": "spell_asset"},
    )
    bus.emit(ctx)
    return ctx


class TestShiningTrapezohedron:
    def test_success_pays_spell_cost(self):
        """意志检定成功（袋中仅0）：法术费用返还，资产留在场上。"""
        state, bus, bag, inv, inst, impl = _setup([ChaosTokenType.ZERO])
        ctx = _simulate_asset_play(bus, state, inv)
        assert inst.exhausted is True
        assert inv.resources == 5  # 3费返还
        assert "spell1" in inv.play_area
        assert ctx.extra["trapezohedron_paid"] == "spell_asset"

    def test_failure_cancels_play(self):
        """意志检定失败（袋中仅-8）：资产弹回手牌、费用与行动返还、本轮封锁。"""
        state, bus, bag, inv, inst, impl = _setup([ChaosTokenType.MINUS_8])
        actions_before = inv.actions_remaining
        ctx = _simulate_asset_play(bus, state, inv)
        assert inv.resources == 5  # 费用返还
        assert "spell1" not in state.cards_in_play
        assert "spell1" not in inv.play_area
        assert "spell_asset" in inv.hand  # 弹回手牌
        assert inv.actions_remaining == actions_before + 1  # 行动费用取消
        assert "spell_asset" in state.scenario.vars["trapezohedron_blocked"]
        assert ctx.extra["trapezohedron_cancelled"] == "spell_asset"

    def test_non_spell_not_intercepted(self):
        """非法术卡不触发。"""
        state, bus, bag, inv, inst, impl = _setup([ChaosTokenType.ZERO])
        state.card_database["tool"] = make_asset_data(id="tool", cost=2,
                                                      traits=["tool"])
        inv.resources -= 2
        bus.emit(EventContext(
            game_state=state, event=GameEvent.RESOURCES_SPENT,
            investigator_id="inv1", amount=2,
        ))
        tool = CardInstance(
            instance_id="tool1", card_id="tool",
            owner_id="inv1", controller_id="inv1",
        )
        state.cards_in_play["tool1"] = tool
        inv.play_area.append("tool1")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target="tool1", extra={"card_id": "tool"},
        ))
        assert inst.exhausted is False
        assert inv.resources == 3  # 无返还

    def test_exhausted_trapezohedron_does_not_trigger(self):
        state, bus, bag, inv, inst, impl = _setup([ChaosTokenType.ZERO])
        inst.exhausted = True
        _simulate_asset_play(bus, state, inv)
        assert inv.resources == 2  # 未返还

    def test_event_cancelled_goes_back_to_hand(self):
        """事件失败：效果取消（ctx.cancel），随后从弃牌堆移回手牌。"""
        state, bus, bag, inv, inst, impl = _setup([ChaosTokenType.MINUS_8])
        state.card_database["spell_event"] = make_asset_data(
            id="spell_event", cost=2, traits=["spell"])
        inv.resources -= 2
        bus.emit(EventContext(
            game_state=state, event=GameEvent.RESOURCES_SPENT,
            investigator_id="inv1", amount=2,
        ))
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1", extra={"card_id": "spell_event"},
        )
        bus.emit(ctx)
        assert ctx.cancelled is True
        assert inv.resources == 5
        # _play_event 随后将事件送入弃牌堆
        inv.discard.append("spell_event")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.ACTION_PERFORMED,
            investigator_id="inv1",
        ))
        assert "spell_event" not in inv.discard
        assert "spell_event" in inv.hand
