"""Tests for Storm of Spirits (Level 0). (03153)

攻击：用意志代替战斗；成功时对被攻击敌人地点的每名敌人造成2点伤害
（被攻击者经 bonus_damage 结算2点）；坏标记对该地点每名调查员造成1点伤害。
"""

import pytest
from backend.cards.mystic.storm_of_spirits_lv0 import StormOfSpirits
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill
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

    inv_data = make_investigator_data(willpower=5, combat=1)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv
    loc_data = make_location_data(id="loc1")
    state.card_database["loc1"] = loc_data
    state.locations["loc1"] = LocationState(
        location_id="loc1", card_data=loc_data, revealed=True,
    )

    state.card_database["storm_of_spirits_lv0"] = make_event_data(
        id="storm_of_spirits_lv0", name="Storm of Spirits", cost=3,
    )
    state.card_database["test_enemy"] = make_enemy_data(id="test_enemy")

    # 被攻击敌人（交战中）+ 同地点另一名敌人（未交战）
    engaged = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    state.cards_in_play["enemy_1"] = engaged
    inv.threat_area.append("enemy_1")
    other = CardInstance(
        instance_id="enemy_2", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    state.cards_in_play["enemy_2"] = other
    state.locations["loc1"].enemies.append("enemy_2")

    impl = StormOfSpirits("inst_storm")
    impl.register(bus, "inst_storm")
    return state, bus, inv, impl


def _play(bus, state):
    bus.emit(EventContext(
        game_state=state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1", extra={"card_id": "storm_of_spirits_lv0"},
    ))


def _fight_initiated(bus, state):
    bus.emit(EventContext(
        game_state=state, event=GameEvent.FIGHT_ACTION_INITIATED,
        investigator_id="inv1", enemy_id="enemy_1",
    ))


class TestStormOfSpirits:
    def test_willpower_substituted_for_combat(self, setup):
        """武装后的战斗检定以意志（5）代替战斗（1）。"""
        state, bus, inv, impl = setup
        _play(bus, state)
        _fight_initiated(bus, state)
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.COMBAT, amount=1,
        )
        bus.emit(ctx)
        assert ctx.amount == 5

    def test_success_deals_2_to_each_enemy_at_location(self, setup):
        """成功：被攻击敌人经 bonus_damage 结算2点，同地点其他敌人各2点。"""
        state, bus, inv, impl = setup
        _play(bus, state)
        _fight_initiated(bus, state)
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1", skill_type=Skill.COMBAT,
            success=True, modified_skill=6, difficulty=3,
        )
        bus.emit(ctx)
        # 被攻击敌人：基础1 + bonus1 = 2（由引擎结算通道）
        assert ctx.extra["bonus_damage"] == 1
        # 同地点另一名敌人直接受到2点
        assert state.cards_in_play["enemy_2"].damage == 2
        # 被攻击敌人本身未被直接加伤（走引擎结算）
        assert state.cards_in_play["enemy_1"].damage == 0
        assert ctx.extra["storm_of_spirits_splash"] is True

    def test_bonus_damage_stacks_on_attacked_enemy(self, setup):
        """已有额外伤害（如 vicious blow）只加给被攻击敌人。"""
        state, bus, inv, impl = setup
        _play(bus, state)
        _fight_initiated(bus, state)
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1", skill_type=Skill.COMBAT,
            success=True, modified_skill=6, difficulty=3,
            extra={"bonus_damage": 1},
        )
        bus.emit(ctx)
        assert ctx.extra["bonus_damage"] == 2  # 1已有 + 1灵魂风暴

    def test_bad_token_damages_investigators_at_location(self, setup):
        """坏标记：检定结束时对该地点每名调查员造成1点伤害（无论成败）。"""
        state, bus, inv, impl = setup
        _play(bus, state)
        _fight_initiated(bus, state)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", skill_type=Skill.COMBAT,
            chaos_token=ChaosTokenType.SKULL,
        ))
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1", success=False,
        )
        bus.emit(ctx)
        assert inv.damage == 1
        assert ctx.extra["storm_of_spirits_backlash"] is True

    def test_no_effect_when_not_armed(self, setup):
        state, bus, inv, impl = setup
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.COMBAT, amount=1,
        )
        bus.emit(ctx)
        assert ctx.amount == 1

    def test_clear_after_test(self, setup):
        """检定结束后武装清除：后续检定不再替换意志。"""
        state, bus, inv, impl = setup
        _play(bus, state)
        _fight_initiated(bus, state)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1", success=True,
        ))
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.COMBAT, amount=1,
        )
        bus.emit(ctx)
        assert ctx.amount == 1
