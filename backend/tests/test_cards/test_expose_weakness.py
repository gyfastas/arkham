"""Tests for Expose Weakness (Level 1)."""

import pytest
from backend.cards.seeker.expose_weakness_lv1 import ExposeWeakness
from backend.engine.event_bus import EventBus, EventContext
from backend.engine.game import Game
from backend.models.chaos import ChaosBag
from backend.models.enums import Action, ChaosTokenType, GameEvent, Skill
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

    inv_data = make_investigator_data(intellect=5, combat=3)
    state.card_database[inv_data.id] = inv_data
    enemy_data = make_enemy_data(fight=3, health=10)
    state.card_database[enemy_data.id] = enemy_data
    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data,
        location_id="test_location", deck=[],
    )
    state.investigators["inv1"] = inv
    loc = LocationState(location_id="test_location", card_data=loc_data, clues=3)
    state.locations["test_location"] = loc

    enemy = CardInstance(
        instance_id="e1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    state.cards_in_play["e1"] = enemy
    loc.enemies.append("e1")

    impl = ExposeWeakness("ew_1")
    impl.register(bus, "ew_1")
    impl.bind_chaos_bag(bag)

    return state, bus, bag, inv, loc, impl


def _play(state, bus):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "expose_weakness_lv1"},
    )
    bus.emit(ctx)
    return ctx


def _next_attack_difficulty(state, bus, difficulty, enemy_id="e1"):
    """模拟对该敌人的下一次攻击：FIGHT 锁定目标后读取战斗检定难度。"""
    bus.emit(EventContext(
        game_state=state, event=GameEvent.FIGHT_ACTION_INITIATED,
        investigator_id="inv1", enemy_id=enemy_id,
    ))
    ctx = EventContext(
        game_state=state, event=GameEvent.SKILL_TEST_BEGINS,
        investigator_id="inv1", skill_type=Skill.COMBAT, difficulty=difficulty,
    )
    bus.emit(ctx)
    return ctx


class TestExposeWeakness:
    def test_success_reduces_fight_by_margin(self, setup):
        """智力5 对战斗力3（0标记）：超2点 → 下一次攻击其战斗力-2。"""
        state, bus, bag, inv, loc, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]

        ctx = _play(state, bus)
        assert ctx.extra["expose_weakness_success"] is True
        assert ctx.extra["expose_weakness_reduction"] == 2

        attack = _next_attack_difficulty(state, bus, difficulty=3)
        assert attack.difficulty == 1
        assert attack.extra["expose_weakness_reduced"] == 2

    def test_reduction_only_for_next_attack(self, setup):
        """减战斗力只对本阶段下一次攻击生效一次。"""
        state, bus, bag, inv, loc, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]

        _play(state, bus)
        first = _next_attack_difficulty(state, bus, difficulty=3)
        assert first.difficulty == 1
        second = _next_attack_difficulty(state, bus, difficulty=3)
        assert second.difficulty == 3  # 不再减

    def test_failure_no_reduction(self, setup):
        """检定失败：不减战斗力。"""
        state, bus, bag, inv, loc, impl = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL]

        ctx = _play(state, bus)
        assert ctx.extra["expose_weakness_success"] is False
        assert "expose_weakness_reduction" not in ctx.extra

        attack = _next_attack_difficulty(state, bus, difficulty=3)
        assert attack.difficulty == 3

    def test_no_enemy_no_test(self, setup):
        """所在地点没有敌人：打出无效果。"""
        state, bus, bag, inv, loc, impl = setup
        loc.enemies.remove("e1")
        ctx = _play(state, bus)
        assert "expose_weakness_success" not in ctx.extra

    def test_full_fight_integration(self):
        """完整流程：暴露弱点后战斗检定难度降低使攻击命中。"""
        g = Game("test_ew")
        g.chaos_bag.seed(42)
        inv_data = make_investigator_data(intellect=5, combat=3)
        g.register_card_data(inv_data)
        enemy_data = make_enemy_data(fight=4, health=5)
        g.register_card_data(enemy_data)
        loc_data = make_location_data()
        g.register_card_data(loc_data)
        g.add_investigator("inv1", inv_data, starting_location="test_location")
        g.add_location("test_location", loc_data, clues=0)

        enemy = CardInstance(
            instance_id="e1", card_id="test_enemy",
            owner_id="scenario", controller_id="scenario",
        )
        g.state.cards_in_play["e1"] = enemy
        inv = g.state.get_investigator("inv1")
        inv.threat_area.append("e1")
        inv.actions_remaining = 3

        impl = ExposeWeakness("ew_1")
        impl.register(g.event_bus, "ew_1")
        impl.bind_chaos_bag(g.chaos_bag)

        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        # 智力5 对战斗力4：超1点 → 下次攻击战斗力-1（难度4→3）
        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "expose_weakness_lv1"},
        ))
        # 战斗3 对难度3（原4减1）：命中造成1伤害；若不减弱则 3<4 失败
        ok = g.action_resolver.perform_action("inv1", Action.FIGHT, enemy_instance_id="e1")
        assert ok is True
        assert enemy.damage == 1
