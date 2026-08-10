"""Tests for Track Shoes (Level 0)."""

import pytest
from backend.cards.survivor.track_shoes_lv0 import TrackShoes
from backend.engine.event_bus import EventBus, EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import Action, ChaosTokenType, GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(agility=3)
    state.card_database[inv_data.id] = inv_data
    loc1 = make_location_data(id="loc1", connections=["loc2"])
    loc2 = make_location_data(id="loc2", connections=["loc1"])
    state.card_database["loc1"] = loc1
    state.card_database["loc2"] = loc2
    state.locations["loc1"] = LocationState(location_id="loc1", card_data=loc1)
    state.locations["loc2"] = LocationState(location_id="loc2", card_data=loc2)

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv

    inst = CardInstance(
        instance_id="ts_inst", card_id="track_shoes_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["ts_inst"] = inst
    inv.play_area.append("ts_inst")

    impl = TrackShoes("ts_inst")
    impl.register(bus, "ts_inst")
    impl.bind_chaos_bag(bag)
    return state, bus, bag, inv, inst


def _move_performed(bus, state):
    ctx = EventContext(
        game_state=state, event=GameEvent.ACTION_PERFORMED,
        investigator_id="inv1", action=Action.MOVE,
    )
    bus.emit(ctx)
    return ctx


class TestTrackShoes:
    def test_static_agility_bonus(self, setup):
        """常驻 +1 敏捷（经 SKILL_VALUE_DETERMINED 修正）。"""
        state, bus, bag, inv, inst = setup
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.AGILITY,
            amount=3, extra={"base_skill": 3},
        )
        bus.emit(ctx)
        assert ctx.amount == 4
        # 其他技能不加
        ctx2 = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.COMBAT,
            amount=3, extra={"base_skill": 3},
        )
        bus.emit(ctx2)
        assert ctx2.amount == 3

    def test_move_success_moves_again(self, setup):
        """移动后：消耗钉鞋，敏捷(3)成功 → 移动到连接地点。"""
        state, bus, bag, inv, inst = setup
        bag.tokens = [ChaosTokenType.ZERO]
        # 敏捷3 + 钉鞋1 + 0 = 4 >= 3
        ctx = _move_performed(bus, state)
        assert inst.exhausted
        assert ctx.extra["track_shoes_success"] is True
        assert inv.location_id == "loc2"

    def test_move_failure_stays(self, setup):
        """敏捷检定失败：不移动。"""
        state, bus, bag, inv, inst = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL]
        ctx = _move_performed(bus, state)
        assert inst.exhausted
        assert ctx.extra["track_shoes_success"] is False
        assert inv.location_id == "loc1"

    def test_exhausted_shoes_no_reaction(self, setup):
        """钉鞋已消耗：移动后不触发。"""
        state, bus, bag, inv, inst = setup
        inst.exhausted = True
        bag.tokens = [ChaosTokenType.ZERO]
        ctx = _move_performed(bus, state)
        assert "track_shoes_success" not in ctx.extra
        assert inv.location_id == "loc1"

    def test_other_actions_ignored(self, setup):
        """非移动行动不触发。"""
        state, bus, bag, inv, inst = setup
        bag.tokens = [ChaosTokenType.ZERO]
        ctx = EventContext(
            game_state=state, event=GameEvent.ACTION_PERFORMED,
            investigator_id="inv1", action=Action.INVESTIGATE,
        )
        bus.emit(ctx)
        assert not inst.exhausted
        assert inv.location_id == "loc1"
