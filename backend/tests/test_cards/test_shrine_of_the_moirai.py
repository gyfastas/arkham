"""Tests for Shrine of the Moirai (Level 3)."""

import pytest
from backend.cards.survivor.shrine_of_the_moirai_lv3 import ShrineOfTheMoirai
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import GameState, InvestigatorState, LocationState, ScenarioState
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)


def _leveled_event(card_id, level):
    data = make_event_data(id=card_id, name=card_id)
    data.level = level
    return data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    for cid, lv in (("card_lv3", 3), ("card_lv2", 2), ("card_lv1", 1)):
        state.card_database[cid] = _leveled_event(cid, lv)

    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data
    state.locations["test_location"] = LocationState(
        location_id="test_location", card_data=loc_data)

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data,
        location_id="test_location",
        discard=["card_lv1", "card_lv2", "card_lv3"],
    )
    state.investigators["inv1"] = inv
    state.scenario.encounter_deck = ["encounter_a", "encounter_b"]

    impl = ShrineOfTheMoirai("shrine_temp")
    impl.register(bus, "shrine_temp")

    ctx = EventContext(
        game_state=state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1", extra={"card_id": "shrine_of_the_moirai_lv3"},
    )
    bus.emit(ctx)
    return state, bus, inv, ctx


class TestShrineOfTheMoirai:
    def test_attaches_to_location_with_offerings(self, setup):
        """打出：叠加到所在地点，3贡品。"""
        state, bus, inv, ctx = setup
        inst_id = ctx.extra["shrine_attached"]
        inst = state.get_card_instance(inst_id)
        loc = state.get_location("test_location")
        assert inst is not None
        assert inst.attached_to == "test_location"
        assert inst.uses["offerings"] == 3
        assert inst_id in loc.attachments

    def test_activate_returns_two_cards(self, setup):
        """启动：回收至多2张、等级合计≤5 的卡牌（贪心 3+2=5）。"""
        state, bus, inv, ctx = setup
        impl = ShrineOfTheMoirai("shrine_temp")
        ok = impl.activate(state, "inv1")
        assert ok
        assert "card_lv3" in inv.hand
        assert "card_lv2" in inv.hand
        assert "card_lv1" in inv.discard  # 3+2=5 已满，1级卡留下
        # 费用：遭遇牌堆顶入遭遇弃牌堆；消耗；贡品-1
        assert state.scenario.encounter_deck == ["encounter_b"]
        assert state.scenario.encounter_discard == ["encounter_a"]
        inst = state.get_card_instance(ctx.extra["shrine_attached"])
        assert inst.exhausted
        assert inst.uses["offerings"] == 2

    def test_activate_requires_same_location(self, setup):
        """不在叠加地点的调查员不能触发。"""
        state, bus, inv, ctx = setup
        inv.location_id = "elsewhere"
        impl = ShrineOfTheMoirai("shrine_temp")
        assert impl.activate(state, "inv1") is False
        assert inv.hand == []

    def test_activate_blocked_when_exhausted(self, setup):
        """已消耗时不能再次触发。"""
        state, bus, inv, ctx = setup
        impl = ShrineOfTheMoirai("shrine_temp")
        assert impl.activate(state, "inv1") is True
        assert impl.activate(state, "inv1") is False
