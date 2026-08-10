"""Tests for Expose Weakness (Level 3)."""

import pytest
from backend.cards.seeker.expose_weakness_lv3 import ExposeWeaknessLv3
from backend.engine.event_bus import EventBus, EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent, Skill
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
    enemy_data = make_enemy_data(fight=4, health=10)
    state.card_database[enemy_data.id] = enemy_data
    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data,
        location_id="test_location", deck=["some_card"],
    )
    state.investigators["inv1"] = inv
    loc = LocationState(location_id="test_location", card_data=loc_data, clues=0)
    state.locations["test_location"] = loc

    enemy = CardInstance(
        instance_id="e1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    state.cards_in_play["e1"] = enemy
    loc.enemies.append("e1")

    impl = ExposeWeaknessLv3("ew3_1")
    impl.register(bus, "ew3_1")
    impl.bind_chaos_bag(bag)

    return state, bus, bag, inv, loc, impl


def _play(state, bus):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "expose_weakness_lv3"},
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


class TestExposeWeaknessLv3:
    def test_success_treats_fight_as_zero(self, setup):
        """成功：本阶段下一次攻击该敌人时其战斗力视为0。"""
        state, bus, bag, inv, loc, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]

        ctx = _play(state, bus)
        assert ctx.extra["expose_weakness_success"] is True

        attack = _next_attack_difficulty(state, bus, difficulty=4)
        assert attack.difficulty == 0
        assert attack.extra["expose_weakness_reduced"] == 4

    def test_draw_card_regardless_of_success(self, setup):
        """"抽取1张卡牌"独立成句：失败也抽。"""
        state, bus, bag, inv, loc, impl = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL]
        hand_before = len(inv.hand)

        ctx = _play(state, bus)
        assert ctx.extra["expose_weakness_success"] is False
        assert ctx.extra["expose_weakness_drew"] is True
        assert len(inv.hand) == hand_before + 1
        # 失败不减战斗力
        attack = _next_attack_difficulty(state, bus, difficulty=4)
        assert attack.difficulty == 4

    def test_reduction_only_next_attack(self, setup):
        """视为0只对本阶段下一次攻击生效一次。"""
        state, bus, bag, inv, loc, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]

        _play(state, bus)
        first = _next_attack_difficulty(state, bus, difficulty=4)
        assert first.difficulty == 0
        second = _next_attack_difficulty(state, bus, difficulty=4)
        assert second.difficulty == 4
