"""Tests for Glimpse the Unthinkable (Level 5)."""

import pytest
from backend.cards.seeker.glimpse_the_unthinkable_lv5 import GlimpseTheUnthinkable
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data
    for cid in ["w1", "w2", "k1"]:
        state.card_database[cid] = make_asset_data(id=cid, cost=2)
    weakness = make_asset_data(id="weak_card", cost=0)
    weakness.subtype = "weakness"
    state.card_database["weak_card"] = weakness

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data,
        location_id="test_location",
        hand=["w1", "weak_card", "w2"],
        deck=["d1", "d2", "d3", "d4", "d5", "d6", "d7", "d8"],
    )
    state.investigators["inv1"] = inv
    state.locations["test_location"] = LocationState(
        location_id="test_location", card_data=loc_data,
    )

    impl = GlimpseTheUnthinkable("gtu_1")
    impl.register(bus, "gtu_1")
    return state, bus, inv, impl


def _play(state, bus, **extra):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "glimpse_the_unthinkable_lv5", **extra},
    )
    bus.emit(ctx)
    return ctx


class TestGlimpseTheUnthinkable:
    def test_shuffle_non_weakness_and_draw_to_max(self, setup):
        """默认混洗全部非弱点手牌（2张），再抽到手牌上限8。"""
        state, bus, inv, impl = setup
        ctx = _play(state, bus)

        assert ctx.extra["glimpse_shuffled"] == 2
        # 混洗后手牌只剩弱点，再抽7张到8张
        assert len(inv.hand) == 8
        assert "weak_card" in inv.hand  # 弱点不混洗
        assert ctx.extra["glimpse_drawn"] == 7

    def test_explicit_shuffle_selection(self, setup):
        """显式指定只混洗1张。"""
        state, bus, inv, impl = setup
        ctx = _play(state, bus, shuffle_card_ids=["w1"])
        assert ctx.extra["glimpse_shuffled"] == 1
        assert len(inv.hand) == 8

    def test_removed_from_game_at_round_end(self, setup):
        """本卡以移出游戏代替弃置（ROUND_ENDS 延迟清理）。"""
        state, bus, inv, impl = setup
        _play(state, bus)
        # 引擎出牌流程会把事件放入弃牌堆
        inv.discard.append("glimpse_the_unthinkable_lv5")

        bus.emit(EventContext(
            game_state=state, event=GameEvent.ROUND_ENDS,
        ))
        assert "glimpse_the_unthinkable_lv5" not in inv.discard
        assert "glimpse_the_unthinkable_lv5" in \
            state.scenario.vars["removed_from_game"]
