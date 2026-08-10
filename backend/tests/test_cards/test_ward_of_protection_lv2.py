"""Tests for Ward of Protection (Level 2). (03270)

快速。任意地点的调查员抽非弱点诡计卡时打出：取消显现效果，持有者受1恐惧。
"""

import pytest
from backend.cards.mystic.ward_of_protection_lv2 import WardOfProtectionLv2
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import CardType, GameEvent, PlayerClass
from backend.models.state import (
    CardData, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
)


def _treachery(id: str, subtype: str = "") -> CardData:
    return CardData(
        id=id, name=id, name_cn=id, type=CardType.TREACHERY,
        card_class=PlayerClass.NEUTRAL, subtype=subtype,
    )


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    holder = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        resources=2, hand=["ward_of_protection_lv2"],
    )
    state.investigators["inv1"] = holder

    inv2_data = make_investigator_data(id="inv2", name="Second")
    state.card_database["inv2"] = inv2_data
    drawer = InvestigatorState(
        investigator_id="inv2", card_data=inv2_data, location_id="loc2",
    )
    state.investigators["inv2"] = drawer

    state.card_database["ward_of_protection_lv2"] = make_event_data(
        id="ward_of_protection_lv2", name="Ward of Protection", cost=1,
        fast=True,
    )
    state.card_database["frozen_in_fear"] = _treachery("frozen_in_fear")
    state.card_database["dark_memory"] = _treachery(
        "dark_memory", subtype="weakness")
    state.card_database["ghoul"] = make_enemy_data(id="ghoul")

    impl = WardOfProtectionLv2("inst_wop2")
    impl.register(bus, "inst_wop2")
    return state, bus, holder, drawer, impl


def _draw(state, bus, card_id, drawer_id="inv2"):
    ctx = EventContext(
        game_state=state, event=GameEvent.ENCOUNTER_CARD_DRAWN,
        investigator_id=drawer_id, extra={"card_id": card_id},
    )
    bus.emit(ctx)
    return ctx


class TestWardOfProtectionLv2:
    def test_cancels_treachery_drawn_by_other_investigator(self, setup):
        """其他地点的调查员抽诡计：持有者自动打出并取消。"""
        state, bus, holder, drawer, impl = setup
        ctx = _draw(state, bus, "frozen_in_fear", drawer_id="inv2")
        assert ctx.extra["ward_of_protection_cancelled"] == "frozen_in_fear"
        assert ctx.extra["ward_of_protection_holder"] == "inv1"
        assert state.scenario.vars["cancelled_encounter"] == "frozen_in_fear"
        # 费用与恐惧由持有者承担
        assert holder.resources == 1
        assert holder.horror == 1
        assert "ward_of_protection_lv2" not in holder.hand
        assert "ward_of_protection_lv2" in holder.discard
        assert drawer.horror == 0

    def test_cancels_own_draw(self, setup):
        state, bus, holder, drawer, impl = setup
        ctx = _draw(state, bus, "frozen_in_fear", drawer_id="inv1")
        assert ctx.extra["ward_of_protection_cancelled"] == "frozen_in_fear"
        assert holder.horror == 1

    def test_ignores_weakness_treachery(self, setup):
        state, bus, holder, drawer, impl = setup
        ctx = _draw(state, bus, "dark_memory", drawer_id="inv2")
        assert "ward_of_protection_cancelled" not in ctx.extra
        assert "ward_of_protection_lv2" in holder.hand
        assert holder.horror == 0

    def test_ignores_enemy_cards(self, setup):
        state, bus, holder, drawer, impl = setup
        ctx = _draw(state, bus, "ghoul", drawer_id="inv2")
        assert "ward_of_protection_cancelled" not in ctx.extra

    def test_no_cancel_without_resources(self, setup):
        state, bus, holder, drawer, impl = setup
        holder.resources = 0
        ctx = _draw(state, bus, "frozen_in_fear", drawer_id="inv2")
        assert "ward_of_protection_cancelled" not in ctx.extra
        assert "ward_of_protection_lv2" in holder.hand

    def test_no_cancel_when_not_in_any_hand(self, setup):
        state, bus, holder, drawer, impl = setup
        holder.hand.remove("ward_of_protection_lv2")
        ctx = _draw(state, bus, "frozen_in_fear", drawer_id="inv2")
        assert "ward_of_protection_cancelled" not in ctx.extra
