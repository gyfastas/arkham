"""Tests for Gaze of Ouraxsh (Level 2)."""

import pytest
from backend.cards.seeker.gaze_of_ouraxsh_lv2 import GazeOfOuraxsh
from backend.engine.event_bus import EventBus, EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    enemy_data = make_enemy_data(fight=3, health=20)
    state.card_database[enemy_data.id] = enemy_data
    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="test_location",
    )
    state.investigators["inv1"] = inv
    loc = LocationState(location_id="test_location", card_data=loc_data, clues=0)
    state.locations["test_location"] = loc

    enemy = CardInstance(
        instance_id="e1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    state.cards_in_play["e1"] = enemy
    inv.threat_area.append("e1")

    impl = GazeOfOuraxsh("gaze_1")
    impl.register(bus, "gaze_1")
    impl.bind_chaos_bag(bag)
    return state, bus, bag, inv, loc, enemy, impl


def _play(state, bus, **extra):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "gaze_of_ouraxsh_lv2", **extra},
    )
    bus.emit(ctx)
    return ctx


class TestGazeOfOuraxsh:
    def test_damage_scales_with_curse_tokens(self, setup):
        """7个标记中每个诅咒/自动失败+1伤害（基础1）。"""
        state, bus, bag, inv, loc, enemy, impl = setup
        bag.tokens = [ChaosTokenType.CURSE] * 7

        ctx = _play(state, bus)
        assert ctx.extra["gaze_damage"] == 8
        assert enemy.damage == 8
        # 揭示的标记结算后放回袋中
        assert len(bag.tokens) == 7

    def test_auto_fail_counts_too(self, setup):
        """自动失败标记同样计入。"""
        state, bus, bag, inv, loc, enemy, impl = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL] * 2 + [ChaosTokenType.ZERO] * 5
        bag.seed(1)

        ctx = _play(state, bus)
        assert ctx.extra["gaze_damage"] == 3
        assert enemy.damage == 3

    def test_damage_split_explicit(self, setup):
        """显式分配：伤害按 damage_split 分到多个敌人。"""
        state, bus, bag, inv, loc, enemy, impl = setup
        enemy2_data = make_enemy_data(id="enemy2", health=20)
        state.card_database["enemy2"] = enemy2_data
        enemy2 = CardInstance(
            instance_id="e2", card_id="enemy2",
            owner_id="scenario", controller_id="scenario",
        )
        state.cards_in_play["e2"] = enemy2
        loc.enemies.append("e2")

        bag.tokens = [ChaosTokenType.CURSE] * 7
        _play(state, bus, damage_split={"e1": 5, "e2": 3})
        assert enemy.damage == 5
        assert enemy2.damage == 3

    def test_kill_defeats_enemy(self, setup):
        """伤害足够时敌人被击败（进遭遇弃牌堆）。"""
        state, bus, bag, inv, loc, enemy, impl = setup
        enemy_data = state.get_card_data("test_enemy")
        enemy_data.enemy_health = 3
        bag.tokens = [ChaosTokenType.CURSE] * 7

        _play(state, bus)
        assert "e1" not in state.cards_in_play
        assert "e1" not in inv.threat_area
        assert "test_enemy" in state.scenario.encounter_discard

    def test_no_enemy_no_effect(self, setup):
        """地点无敌人：不揭示标记。"""
        state, bus, bag, inv, loc, enemy, impl = setup
        inv.threat_area.remove("e1")
        bag.tokens = [ChaosTokenType.CURSE] * 7
        ctx = _play(state, bus)
        assert "gaze_damage" not in ctx.extra
