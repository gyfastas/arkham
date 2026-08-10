"""Tests for Connect the Dots (Level 0). (05025)

快速。你发现所在地点最后1条线索后打出：在印刷隐蔽值更低的地点发现2条线索。
"""

import pytest

from backend.cards.seeker.connect_the_dots_lv0 import ConnectTheDots
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc_high",
        resources=5,
    )
    state.investigators["inv1"] = inv

    high = make_location_data(id="loc_high", shroud=4)
    low = make_location_data(id="loc_low", shroud=2)
    low2 = make_location_data(id="loc_low2", shroud=3)
    for ld in (high, low, low2):
        state.card_database[ld.id] = ld
    state.locations["loc_high"] = LocationState(
        location_id="loc_high", card_data=high, clues=0)
    state.locations["loc_low"] = LocationState(
        location_id="loc_low", card_data=low, clues=2)
    state.locations["loc_low2"] = LocationState(
        location_id="loc_low2", card_data=low2, clues=1)

    state.card_database["connect_the_dots_lv0"] = make_event_data(
        id="connect_the_dots_lv0", name="Connect the Dots", cost=4, fast=True)
    inv.hand = ["connect_the_dots_lv0"]

    impl = ConnectTheDots("inst_ctd")
    impl.register(bus, "inst_ctd")
    return state, bus, inv, impl


def _last_clue_discovered(state, bus, loc_id="loc_high"):
    ctx = EventContext(
        game_state=state, event=GameEvent.CLUE_DISCOVERED,
        investigator_id="inv1", location_id=loc_id, amount=1,
    )
    bus.emit(ctx)
    return ctx


class TestConnectTheDots:
    def test_auto_play_after_last_clue(self, setup):
        """发现最后1条线索后自动打出：在更低隐蔽地点发现2条。"""
        state, bus, inv, impl = setup
        ctx = _last_clue_discovered(state, bus)
        assert ctx.extra.get("connect_the_dots_played") == "loc_low"
        assert "connect_the_dots_lv0" not in inv.hand
        assert "connect_the_dots_lv0" in inv.discard
        assert inv.resources == 1  # 5 - 4
        assert state.locations["loc_low"].clues == 0
        assert inv.clues == 2

    def test_no_trigger_while_clues_remain(self, setup):
        """地点仍有余线索（非最后1条）：不打出。"""
        state, bus, inv, impl = setup
        state.locations["loc_high"].clues = 2
        ctx = _last_clue_discovered(state, bus)
        assert "connect_the_dots_played" not in ctx.extra
        assert "connect_the_dots_lv0" in inv.hand

    def test_no_lower_shroud_target_no_play(self, setup):
        """无更低印刷隐蔽的目标地点：不打出。"""
        state, bus, inv, impl = setup
        state.locations["loc_low"].clues = 0
        state.locations["loc_low2"].clues = 0
        ctx = _last_clue_discovered(state, bus)
        assert "connect_the_dots_played" not in ctx.extra
        assert "connect_the_dots_lv0" in inv.hand
