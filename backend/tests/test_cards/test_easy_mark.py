"""Tests for Easy Mark (Level 1)."""

import pytest
from backend.cards.rogue.easy_mark_lv1 import EasyMark
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import GameState, InvestigatorState, ScenarioState
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
    inv.hand = ["easy_mark_lv1", "other_card"]
    inv.deck = ["deck_a", "deck_b", "deck_c"]
    state.investigators["inv1"] = inv

    impl = EasyMark("em_inst")
    impl.register(bus, "em_inst")
    return state, bus, inv, impl


def _play(bus, state, depth=0):
    ctx = EventContext(
        game_state=state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "easy_mark_lv1", "easy_mark_chain_depth": depth},
    )
    bus.emit(ctx)
    return ctx


class TestEasyMark:
    def test_gain_2_and_draw_1(self, setup):
        """获得2资源并抽1张牌。"""
        state, bus, inv, impl = setup
        inv.hand = ["other_card"]  # 无第二张，不连锁
        _play(bus, state)
        assert inv.resources == 7
        assert inv.hand == ["other_card", "deck_a"]

    def test_chain_plays_second_copy_free(self, setup):
        """连锁：自动从手牌免费打出另一张冤大头（再+2资源抽1张）。"""
        state, bus, inv, impl = setup
        _play(bus, state)
        assert inv.resources == 9  # 5+2+2
        assert inv.hand == ["other_card", "deck_a", "deck_b"]
        assert inv.discard == ["easy_mark_lv1"]  # 连锁那张入弃牌堆

    def test_chain_of_three(self, setup):
        """手牌3张（多重上限）：连锁两次后停止。"""
        state, bus, inv, impl = setup
        inv.hand = ["easy_mark_lv1", "easy_mark_lv1", "other_card"]
        _play(bus, state)
        assert inv.resources == 11  # 5+2×3
        assert inv.hand == ["other_card", "deck_a", "deck_b", "deck_c"]
        assert inv.discard == ["easy_mark_lv1", "easy_mark_lv1"]
