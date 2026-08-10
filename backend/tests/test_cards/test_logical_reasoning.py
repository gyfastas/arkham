"""Tests for Logical Reasoning (Level 0).

官方：仅有至少1条线索时才能打出。选择你所在地点1位调查员：
治愈2点恐惧，或丢弃其威胁区中1张[[Terror]]卡。
"""

import pytest

from backend.cards.seeker.logical_reasoning_lv0 import LogicalReasoning
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import CardType, GameEvent, PlayerClass
from backend.models.state import (
    CardData, CardInstance, GameState, InvestigatorState, LocationState,
    ScenarioState,
)
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    loc_data = make_location_data(id="loc_a")
    state.card_database[loc_data.id] = loc_data
    state.locations["loc_a"] = LocationState(
        location_id="loc_a", card_data=loc_data)

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc_a",
    )
    inv.clues = 1
    inv.horror = 2
    state.investigators["inv1"] = inv

    state.card_database["logical_reasoning_lv0"] = CardData(
        id="logical_reasoning_lv0", name="Logical Reasoning",
        name_cn="逻辑推理", type=CardType.EVENT,
        card_class=PlayerClass.SEEKER, cost=2,
    )
    state.card_database["chronophobia_lv0"] = CardData(
        id="chronophobia_lv0", name="Chronophobia", name_cn="时间恐惧症",
        type=CardType.TREACHERY, card_class=PlayerClass.NEUTRAL,
        subtype="basic_weakness", traits=["terror"],
    )

    impl = LogicalReasoning("lr_temp")
    impl.register(bus, "lr_temp")
    return state, bus, inv, impl


def _play(state, bus, extra=None):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "logical_reasoning_lv0", **(extra or {})},
    )
    bus.emit(ctx)
    return ctx


def _attach_terror(state, inv):
    inst = CardInstance(
        instance_id="inst_terror", card_id="chronophobia_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_terror"] = inst
    inv.threat_area.append("inst_terror")


class TestLogicalReasoning:
    def test_heals_2_horror(self, setup):
        state, bus, inv, impl = setup
        ctx = _play(state, bus)
        assert inv.horror == 0
        assert ctx.extra["logical_reasoning_healed"] == 2

    def test_heal_caps_at_current_horror(self, setup):
        state, bus, inv, impl = setup
        inv.horror = 1
        ctx = _play(state, bus)
        assert inv.horror == 0
        assert ctx.extra["logical_reasoning_healed"] == 1

    def test_discards_terror_from_threat_area(self, setup):
        """威胁区有Terror卡时默认丢弃之（优先于治愈）。"""
        state, bus, inv, impl = setup
        _attach_terror(state, inv)
        ctx = _play(state, bus)
        assert ctx.extra["logical_reasoning_discarded"] == "chronophobia_lv0"
        assert inv.threat_area == []
        assert "chronophobia_lv0" in inv.discard
        assert "inst_terror" not in state.cards_in_play
        assert inv.horror == 2  # 未治愈

    def test_forced_heal_mode(self, setup):
        """显式 mode="heal" 时即使有Terror卡也治愈。"""
        state, bus, inv, impl = setup
        _attach_terror(state, inv)
        ctx = _play(state, bus, extra={"mode": "heal"})
        assert ctx.extra["logical_reasoning_healed"] == 2
        assert "inst_terror" in inv.threat_area

    def test_requires_a_clue(self, setup):
        """打出者没有线索：效果不生效。"""
        state, bus, inv, impl = setup
        inv.clues = 0
        ctx = _play(state, bus)
        assert ctx.extra["logical_reasoning_failed"] == "no_clue"
        assert inv.horror == 2
