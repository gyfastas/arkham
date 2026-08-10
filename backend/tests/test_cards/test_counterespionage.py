"""Tests for Counterespionage (Level 1)."""

import pytest
from backend.cards.rogue.counterespionage_lv1 import Counterespionage
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import CardType, GameEvent, PlayerClass
from backend.models.state import (
    CardData, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data


def _treachery(card_id, subtype=""):
    return CardData(
        id=card_id, name=card_id, name_cn=card_id, type=CardType.TREACHERY,
        card_class=PlayerClass.NEUTRAL, subtype=subtype,
    )


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
    inv.hand = ["counterespionage_lv1"]
    state.investigators["inv1"] = inv

    state.card_database["treachery_a"] = _treachery("treachery_a")
    state.card_database["treachery_b"] = _treachery("treachery_b")
    state.card_database["weak_t"] = _treachery("weak_t", subtype="weakness")
    state.scenario.encounter_deck = ["treachery_b"]

    impl = Counterespionage("ce_inst")
    impl.register(bus, "ce_inst")
    return state, bus, inv, impl


class TestCounterespionage:
    def test_cancel_treachery_and_draw_encounter_top(self, setup):
        """取消非弱点诡计显现，并抽取遭遇牌堆顶。"""
        state, bus, inv, impl = setup
        drawn_events = []
        bus.register(
            event=GameEvent.ENCOUNTER_CARD_DRAWN,
            handler=lambda c: drawn_events.append(c.extra.get("card_id")),
        )
        ctx = EventContext(
            game_state=state, event=GameEvent.ENCOUNTER_CARD_DRAWN,
            investigator_id="inv1", extra={"card_id": "treachery_a"},
        )
        bus.emit(ctx)

        assert state.scenario.vars["cancelled_encounter"] == "treachery_a"
        assert ctx.extra["counterespionage_cancelled"] == "treachery_a"
        assert inv.resources == 3  # 5-2
        assert "counterespionage_lv1" not in inv.hand
        assert "counterespionage_lv1" in inv.discard
        # 遭遇牌堆顶被抽走并发出抽取事件
        assert state.scenario.encounter_deck == []
        assert ctx.extra["counterespionage_drew_encounter"] == "treachery_b"
        assert "treachery_b" in drawn_events
        # 嵌套抽到的诡计不再触发（手牌已无本卡）
        assert "cancelled_encounter" in state.scenario.vars
        assert state.scenario.vars["cancelled_encounter"] == "treachery_a"

    def test_weakness_treachery_not_cancelled(self, setup):
        """弱点诡计不触发。"""
        state, bus, inv, impl = setup
        ctx = EventContext(
            game_state=state, event=GameEvent.ENCOUNTER_CARD_DRAWN,
            investigator_id="inv1", extra={"card_id": "weak_t"},
        )
        bus.emit(ctx)
        assert "cancelled_encounter" not in state.scenario.vars
        assert inv.resources == 5

    def test_not_cancelled_without_resources(self, setup):
        state, bus, inv, impl = setup
        inv.resources = 1
        ctx = EventContext(
            game_state=state, event=GameEvent.ENCOUNTER_CARD_DRAWN,
            investigator_id="inv1", extra={"card_id": "treachery_a"},
        )
        bus.emit(ctx)
        assert "cancelled_encounter" not in state.scenario.vars

    def test_boost_deck_draws_own_deck(self, setup):
        """升级（+2费）：改抽自己牌堆顶。"""
        state, bus, inv, impl = setup
        inv.deck = ["own_card"]
        ctx = EventContext(
            game_state=state, event=GameEvent.ENCOUNTER_CARD_DRAWN,
            investigator_id="inv1",
            extra={"card_id": "treachery_a",
                   "counterespionage_boost_deck": True},
        )
        bus.emit(ctx)
        assert inv.resources == 1  # 5-2-2
        assert inv.hand == ["own_card"]
        assert state.scenario.encounter_deck == ["treachery_b"]
