"""Tests for Time Warp (Level 2). (03311)

快速。同地点调查员结算完毕一次行动后打出：撤销该行动
（简化：返还1行动点；完整状态回滚为引擎缺口）。
"""

import pytest
from backend.cards.mystic.time_warp_lv2 import TimeWarp
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_event_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        actions_remaining=3,
    )
    state.investigators["inv1"] = inv

    inv2_data = make_investigator_data(id="inv2", name="Second")
    state.card_database["inv2"] = inv2_data
    inv2 = InvestigatorState(
        investigator_id="inv2", card_data=inv2_data, location_id="loc1",
        actions_remaining=0,
    )
    state.investigators["inv2"] = inv2

    state.card_database["time_warp_lv2"] = make_event_data(
        id="time_warp_lv2", name="Time Warp", cost=1, fast=True,
    )

    impl = TimeWarp("inst_tw")
    impl.register(bus, "inst_tw")
    return state, bus, inv, inv2, impl


def _play(bus, state, **extra):
    ctx = EventContext(
        game_state=state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1", extra={"card_id": "time_warp_lv2", **extra},
    )
    bus.emit(ctx)
    return ctx


class TestTimeWarp:
    def test_refunds_action_to_current_turn_investigator(self, setup):
        """默认目标：当前回合行动者（同地点）返还1行动点。"""
        state, bus, inv, inv2, impl = setup
        bus.emit(EventContext(
            game_state=state, event=GameEvent.INVESTIGATOR_TURN_BEGINS,
            investigator_id="inv2",
        ))
        ctx = _play(bus, state)
        assert inv2.actions_remaining == 1
        assert ctx.extra["time_warp_undone_for"] == "inv2"

    def test_explicit_target(self, setup):
        state, bus, inv, inv2, impl = setup
        ctx = _play(bus, state, target_investigator_id="inv2")
        assert inv2.actions_remaining == 1
        assert ctx.extra["time_warp_undone_for"] == "inv2"

    def test_target_must_be_at_same_location(self, setup):
        """目标不在同地点时不生效。"""
        state, bus, inv, inv2, impl = setup
        inv2.location_id = "loc2"
        ctx = _play(bus, state, target_investigator_id="inv2")
        assert inv2.actions_remaining == 0
        assert "time_warp_undone_for" not in ctx.extra

    def test_defaults_to_self_without_turn_info(self, setup):
        """无回合信息时默认撤销自己的行动。"""
        state, bus, inv, inv2, impl = setup
        inv.actions_remaining = 2
        ctx = _play(bus, state)
        assert inv.actions_remaining == 3
        assert ctx.extra["time_warp_undone_for"] == "inv1"
