"""Tests for Borrowed Time (Level 3)."""

import pytest
from backend.cards.rogue.borrowed_time_lv3 import BorrowedTime
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
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    inv.resources = 5
    inv.actions_remaining = 3
    state.investigators["inv1"] = inv

    impl = BorrowedTime("bt_inst")
    impl.register(bus, "bt_inst")
    ci = CardInstance(
        instance_id="bt_inst", card_id="borrowed_time_lv3",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["bt_inst"] = ci
    inv.play_area.append("bt_inst")
    return state, bus, inv, impl, ci


class TestBorrowedTime:
    def test_add_click_spends_resource(self, setup):
        """[行动]放1滴答：花费1资源，卡上+1滴答。"""
        state, bus, inv, impl, ci = setup
        assert impl.add_click(state, "inv1") is True
        assert inv.resources == 4
        assert ci.uses["clicks"] == 1

    def test_max_three_clicks(self, setup):
        state, bus, inv, impl, ci = setup
        for _ in range(3):
            assert impl.add_click(state, "inv1") is True
        assert impl.add_click(state, "inv1") is False
        assert inv.resources == 2
        assert ci.uses["clicks"] == 3

    def test_turn_begins_converts_clicks_to_actions(self, setup):
        """回合开始：移除所有滴答，换成等量额外行动。"""
        state, bus, inv, impl, ci = setup
        impl.add_click(state, "inv1")
        impl.add_click(state, "inv1")
        bus.emit(EventContext(
            game_state=state,
            event=GameEvent.INVESTIGATOR_TURN_BEGINS,
            investigator_id="inv1",
        ))
        assert ci.uses["clicks"] == 0
        assert inv.actions_remaining == 5

    def test_no_clicks_no_actions(self, setup):
        state, bus, inv, impl, ci = setup
        bus.emit(EventContext(
            game_state=state,
            event=GameEvent.INVESTIGATOR_TURN_BEGINS,
            investigator_id="inv1",
        ))
        assert inv.actions_remaining == 3

    def test_other_investigator_turn_no_effect(self, setup):
        """其他调查员的回合开始不触发。"""
        state, bus, inv, impl, ci = setup
        other_data = make_investigator_data(id="inv2", name="Other")
        state.card_database["inv2"] = other_data
        other = InvestigatorState(
            investigator_id="inv2", card_data=other_data, location_id="loc1",
        )
        other.actions_remaining = 3
        state.investigators["inv2"] = other

        impl.add_click(state, "inv1")
        bus.emit(EventContext(
            game_state=state,
            event=GameEvent.INVESTIGATOR_TURN_BEGINS,
            investigator_id="inv2",
        ))
        assert ci.uses["clicks"] == 1  # 未消耗
        assert other.actions_remaining == 3
