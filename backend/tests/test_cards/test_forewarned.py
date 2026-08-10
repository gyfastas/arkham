"""Tests for Forewarned (Level 1).

官方：快速。在你抽取1张非弱点诡计卡时打出。将你的1条线索放置到
你所在地点，然后取消该卡的显现效果。
"""

import pytest

from backend.cards.seeker.forewarned_lv1 import Forewarned
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import CardType, GameEvent, PlayerClass
from backend.models.state import (
    CardData, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data, make_location_data


def _treachery(card_id, subtype=""):
    return CardData(
        id=card_id, name=card_id, name_cn="测试诡计",
        type=CardType.TREACHERY, card_class=PlayerClass.NEUTRAL,
        subtype=subtype,
    )


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    loc_data = make_location_data(id="loc_a", clue_value=0)
    state.card_database[loc_data.id] = loc_data
    state.locations["loc_a"] = LocationState(
        location_id="loc_a", card_data=loc_data, clues=0)

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc_a",
    )
    inv.hand = ["forewarned_lv1"]
    inv.clues = 1
    state.investigators["inv1"] = inv

    state.card_database["forewarned_lv1"] = CardData(
        id="forewarned_lv1", name="Forewarned", name_cn="预知",
        type=CardType.EVENT, card_class=PlayerClass.SEEKER, cost=0,
    )
    state.card_database["frozen_in_fear"] = _treachery("frozen_in_fear")
    state.card_database["chronophobia_lv0"] = _treachery(
        "chronophobia_lv0", subtype="basic_weakness")

    impl = Forewarned("fw_impl")
    impl.register(bus, "fw_impl")
    return state, bus, inv, impl


def _draw_encounter(state, bus, card_id):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.ENCOUNTER_CARD_DRAWN,
        investigator_id="inv1",
        extra={"card_id": card_id},
    )
    bus.emit(ctx)
    return ctx


class TestForewarned:
    def test_cancels_treachery_by_placing_clue(self, setup):
        """放置1条线索到所在地点，取消诡计显现。"""
        state, bus, inv, impl = setup
        loc = state.get_location("loc_a")
        ctx = _draw_encounter(state, bus, "frozen_in_fear")

        assert state.scenario.vars["cancelled_encounter"] == "frozen_in_fear"
        assert ctx.extra["forewarned_cancelled"] == "frozen_in_fear"
        assert inv.clues == 0
        assert loc.clues == 1
        assert "forewarned_lv1" in inv.discard
        assert "forewarned_lv1" not in inv.hand

    def test_no_clue_no_trigger(self, setup):
        """没有线索可放置时不触发。"""
        state, bus, inv, impl = setup
        inv.clues = 0
        _draw_encounter(state, bus, "frozen_in_fear")
        assert "cancelled_encounter" not in state.scenario.vars
        assert "forewarned_lv1" in inv.hand

    def test_weakness_treachery_not_cancelled(self, setup):
        """弱点诡计不能取消。"""
        state, bus, inv, impl = setup
        _draw_encounter(state, bus, "chronophobia_lv0")
        assert "cancelled_encounter" not in state.scenario.vars
        assert "forewarned_lv1" in inv.hand

    def test_not_in_hand_no_trigger(self, setup):
        state, bus, inv, impl = setup
        inv.hand = []
        _draw_encounter(state, bus, "frozen_in_fear")
        assert "cancelled_encounter" not in state.scenario.vars
