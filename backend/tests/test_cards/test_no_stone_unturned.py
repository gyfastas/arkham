"""Tests for No Stone Unturned (Level 0 / Level 5).

lv0：选择你所在地点1位调查员，检索其牌库顶6张中的1张，抽取并洗混。
lv5：快速；检索范围为整个牌库。
"""

import pytest

from backend.cards.seeker.no_stone_unturned_lv0 import NoStoneUnturned
from backend.cards.seeker.no_stone_unturned_lv5 import NoStoneUnturnedLv5
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    GameState, InvestigatorState, LocationState, ScenarioState,
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
        deck=[f"card_{i}" for i in range(1, 9)],
    )
    state.investigators["inv1"] = inv

    impl0 = NoStoneUnturned("nsu0_temp")
    impl0.register(bus, "nsu0_temp")
    impl5 = NoStoneUnturnedLv5("nsu5_temp")
    impl5.register(bus, "nsu5_temp")
    return state, bus, inv


def _play(state, bus, card_id, extra=None):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": card_id, **(extra or {})},
    )
    bus.emit(ctx)
    return ctx


class TestNoStoneUnturnedLv0:
    def test_searches_top6_and_draws(self, setup):
        """默认自动抽取顶6张中的第1张，其余洗回。"""
        state, bus, inv = setup
        ctx = _play(state, bus, "no_stone_unturned_lv0")
        assert ctx.extra["no_stone_unturned_drawn"] == "card_1"
        assert "card_1" in inv.hand
        assert len(inv.deck) == 7

    def test_explicit_pick_within_top6(self, setup):
        state, bus, inv = setup
        ctx = _play(state, bus, "no_stone_unturned_lv0",
                    extra={"search_pick": "card_5"})
        assert ctx.extra["no_stone_unturned_drawn"] == "card_5"
        assert "card_5" in inv.hand
        assert len(inv.deck) == 7

    def test_pick_beyond_top6_falls_back(self, setup):
        """lv0 检索范围仅顶6张：指定第8张时回退为第1张。"""
        state, bus, inv = setup
        ctx = _play(state, bus, "no_stone_unturned_lv0",
                    extra={"search_pick": "card_8"})
        assert ctx.extra["no_stone_unturned_drawn"] == "card_1"

    def test_empty_deck_noop(self, setup):
        state, bus, inv = setup
        inv.deck = []
        ctx = _play(state, bus, "no_stone_unturned_lv0")
        assert "no_stone_unturned_drawn" not in ctx.extra
        assert inv.hand == []


class TestNoStoneUnturnedLv5:
    def test_searches_entire_deck(self, setup):
        """lv5 可检索整个牌库（第8张也可选）。"""
        state, bus, inv = setup
        ctx = _play(state, bus, "no_stone_unturned_lv5",
                    extra={"search_pick": "card_8"})
        assert ctx.extra["no_stone_unturned_drawn"] == "card_8"
        assert "card_8" in inv.hand
        assert len(inv.deck) == 7

    def test_default_draws_first_card(self, setup):
        state, bus, inv = setup
        ctx = _play(state, bus, "no_stone_unturned_lv5")
        assert ctx.extra["no_stone_unturned_drawn"] == "card_1"

    def test_other_card_id_not_triggered(self, setup):
        state, bus, inv = setup
        ctx = _play(state, bus, "some_other_event")
        assert "no_stone_unturned_drawn" not in ctx.extra
        assert len(inv.deck) == 8
