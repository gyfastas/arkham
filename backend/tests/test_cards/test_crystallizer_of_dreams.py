"""Tests for Crystallizer of Dreams (Level 0)."""

import pytest
from backend.cards.rogue.crystallizer_of_dreams_lv0 import CrystallizerOfDreams
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import Action, GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_event_data, make_investigator_data


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
    state.card_database["event_x"] = make_event_data(id="event_x", name="Event X")

    impl = CrystallizerOfDreams("cry_inst")
    impl.register(bus, "cry_inst")
    ci = CardInstance(
        instance_id="cry_inst", card_id="crystallizer_of_dreams_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["cry_inst"] = ci
    inv.play_area.append("cry_inst")
    return state, bus, inv, impl, ci


def _play_event(bus, state, inv, card_id="event_x"):
    """模拟引擎的打出流程：CARD_PLAYED → 入弃牌堆 → ACTION_PERFORMED。"""
    bus.emit(EventContext(
        game_state=state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1", extra={"card_id": card_id},
    ))
    inv.discard.append(card_id)  # 引擎在 CARD_PLAYED 结算后放入弃牌堆
    bus.emit(EventContext(
        game_state=state, event=GameEvent.ACTION_PERFORMED,
        investigator_id="inv1", action=Action.PLAY,
    ))


class TestCrystallizerOfDreams:
    def test_event_attached_instead_of_discarded(self, setup):
        """打出事件后：叠加到结晶器而非留在弃牌堆。"""
        state, bus, inv, impl, ci = setup
        _play_event(bus, state, inv)
        assert impl.attached == ["event_x"]
        assert "event_x" not in inv.discard

    def test_max_five_attached(self, setup):
        """最多叠加5张；第6张正常弃置。"""
        state, bus, inv, impl, ci = setup
        for _ in range(6):
            _play_event(bus, state, inv)
        assert impl.attached == ["event_x"] * 5
        assert inv.discard == ["event_x"]

    def test_other_investigator_event_not_attached(self, setup):
        """其他调查员打出的事件不叠加。"""
        state, bus, inv, impl, ci = setup
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv2", extra={"card_id": "event_x"},
        ))
        bus.emit(EventContext(
            game_state=state, event=GameEvent.ACTION_PERFORMED,
            investigator_id="inv2", action=Action.PLAY,
        ))
        assert impl.attached == []

    def test_can_commit_and_consume(self, setup):
        """叠加的事件可被会话层当作手牌投入，投入后入弃牌堆。"""
        state, bus, inv, impl, ci = setup
        _play_event(bus, state, inv)
        assert impl.can_commit("event_x") is True
        assert impl.consume_attached(state, "event_x") is True
        assert impl.attached == []
        assert inv.discard == ["event_x"]
        assert impl.can_commit("event_x") is False
