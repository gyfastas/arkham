"""Tests for Short Supply (Level 0)."""

import pytest
from backend.cards.survivor.short_supply_lv0 import ShortSupply
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data,
        location_id="loc1",
        deck=[f"deck_card_{i}" for i in range(12)],
    )
    state.investigators["inv1"] = inv

    inst = CardInstance(
        instance_id="ss_inst", card_id="short_supply_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["ss_inst"] = inst
    inv.play_area.append("ss_inst")

    impl = ShortSupply("ss_inst")
    impl.register(bus, "ss_inst")
    return state, bus, inv, impl


def _turn_begins(bus, state, investigator_id="inv1"):
    ctx = EventContext(
        game_state=state, event=GameEvent.INVESTIGATOR_TURN_BEGINS,
        investigator_id=investigator_id,
    )
    bus.emit(ctx)
    return ctx


class TestShortSupply:
    def test_first_turn_discards_top_10(self, setup):
        """第一个回合开始：丢弃牌堆顶10张。"""
        state, bus, inv, impl = setup
        ctx = _turn_begins(bus, state)
        assert len(inv.deck) == 2
        assert len(inv.discard) == 10
        # 丢弃的是牌堆顶部的10张（保持顺序）
        assert inv.discard[0] == "deck_card_0"
        assert inv.discard[-1] == "deck_card_9"
        assert ctx.extra["short_supply_discarded"] == 10

    def test_triggers_only_once(self, setup):
        """只触发一次：后续回合开始不再丢弃。"""
        state, bus, inv, impl = setup
        _turn_begins(bus, state)
        _turn_begins(bus, state)
        assert len(inv.deck) == 2
        assert len(inv.discard) == 10

    def test_fewer_than_10_cards(self, setup):
        """牌堆不足10张：全部丢弃。"""
        state, bus, inv, impl = setup
        inv.deck = inv.deck[:4]
        ctx = _turn_begins(bus, state)
        assert len(inv.deck) == 0
        assert len(inv.discard) == 4
        assert ctx.extra["short_supply_discarded"] == 4

    def test_ignores_other_investigators_turn(self, setup):
        """其他调查员的回合开始不触发。"""
        state, bus, inv, impl = setup
        _turn_begins(bus, state, investigator_id="inv2")
        assert len(inv.deck) == 12
        assert len(inv.discard) == 0
