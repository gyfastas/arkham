"""Tests for Mind Wipe (Level 1). (01068)

快速。阶段开始后打出：选所在地点一个非精英敌人，文本框视为空白直到本阶段结束。
"""

import pytest
from backend.cards.mystic.mind_wipe_lv1 import MindWipe
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
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
    state.investigators["inv1"] = inv

    loc_data = make_location_data(id="loc1")
    state.card_database[loc_data.id] = loc_data
    state.locations["loc1"] = LocationState(location_id="loc1", card_data=loc_data)

    state.card_database["mind_wipe_lv1"] = make_event_data(
        id="mind_wipe_lv1", name="Mind Wipe",
    )
    state.card_database["test_enemy"] = make_enemy_data(id="test_enemy")
    elite = make_enemy_data(id="elite_enemy", keywords=["elite"])
    state.card_database["elite_enemy"] = elite

    enemy = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    state.cards_in_play["enemy_1"] = enemy
    state.locations["loc1"].enemies.append("enemy_1")

    impl = MindWipe("inst_mw")
    impl.register(bus, "inst_mw")
    return state, bus, inv, enemy, impl


def _play(state, bus, **extra):
    ctx = EventContext(
        game_state=state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "mind_wipe_lv1", **extra},
    )
    bus.emit(ctx)
    return ctx


class TestMindWipe:
    def test_blanks_first_non_elite_enemy_at_location(self, setup):
        state, bus, inv, enemy, impl = setup
        ctx = _play(state, bus)
        assert ctx.extra["mind_wiped_enemy"] == "enemy_1"
        assert state.scenario.vars["mind_wiped"] == {"enemy_1": True}

    def test_elite_enemy_rejected(self, setup):
        """精英敌人不可选。"""
        state, bus, inv, enemy, impl = setup
        elite = CardInstance(
            instance_id="enemy_elite", card_id="elite_enemy",
            owner_id="scenario", controller_id="scenario",
        )
        state.cards_in_play["enemy_elite"] = elite
        ctx = _play(state, bus, enemy_instance_id="enemy_elite")
        assert "mind_wiped_enemy" not in ctx.extra
        assert "mind_wiped" not in state.scenario.vars

    def test_cleared_at_any_phase_end(self, setup):
        """任意阶段结束时清除（官方：直到本阶段结束）。"""
        state, bus, inv, enemy, impl = setup
        for phase_end in (
            GameEvent.MYTHOS_PHASE_ENDS, GameEvent.INVESTIGATION_PHASE_ENDS,
            GameEvent.ENEMY_PHASE_ENDS, GameEvent.UPKEEP_PHASE_ENDS,
        ):
            _play(state, bus)
            assert "mind_wiped" in state.scenario.vars
            bus.emit(EventContext(game_state=state, event=phase_end))
            assert "mind_wiped" not in state.scenario.vars
