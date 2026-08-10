"""Tests for Banish (Level 1). (05113)

躲避（仅非精英）：意志代替敏捷；成功则把敌人移到任意地点；
若揭示坏符号，敌人下个补给阶段不准备。
"""

import pytest
from backend.cards.mystic.banish_lv1 import Banish
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data(willpower=5, agility=2)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv

    for loc_id in ("loc1", "loc2"):
        loc_data = make_location_data(id=loc_id)
        state.card_database[loc_id] = loc_data
        state.locations[loc_id] = LocationState(
            location_id=loc_id, card_data=loc_data)

    state.card_database["banish_lv1"] = make_event_data(
        id="banish_lv1", name="Banish", cost=2)
    state.card_database["test_enemy"] = make_enemy_data()

    enemy = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    state.cards_in_play["enemy_1"] = enemy

    impl = Banish("impl_banish")
    impl.register(bus, "impl_banish")
    return state, bus, inv, enemy, impl


def _play(state, bus):
    bus.emit(EventContext(
        game_state=state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1", extra={"card_id": "banish_lv1"},
    ))


def _evade_flow(state, bus, token=None):
    bus.emit(EventContext(
        game_state=state, event=GameEvent.EVADE_ACTION_INITIATED,
        investigator_id="inv1", enemy_id="enemy_1",
    ))
    ctx = EventContext(
        game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1", skill_type=Skill.AGILITY, amount=2,
    )
    bus.emit(ctx)
    if token is not None:
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=token, amount=0,
        ))
    return ctx


class TestBanish:
    def test_willpower_substitute(self, setup):
        """躲避检定：意志(5)代替敏捷(2)。"""
        state, bus, inv, enemy, impl = setup
        _play(state, bus)
        ctx = _evade_flow(state, bus)
        assert ctx.amount == 5

    def test_success_moves_enemy_to_other_location(self, setup):
        """成功：敌人被移动到另一个地点。"""
        state, bus, inv, enemy, impl = setup
        _play(state, bus)
        # 模拟引擎躲避成功：敌人横置并放回 loc1
        enemy.exhausted = True
        state.locations["loc1"].enemies.append("enemy_1")
        _evade_flow(state, bus)
        ctx = EventContext(
            game_state=state, event=GameEvent.ENEMY_EVADED,
            investigator_id="inv1", enemy_id="enemy_1",
        )
        bus.emit(ctx)
        assert "enemy_1" in state.locations["loc2"].enemies
        assert "enemy_1" not in state.locations["loc1"].enemies
        assert ctx.extra["banish_moved_to"] == "loc2"

    def test_bad_token_prevents_next_upkeep_ready(self, setup):
        """坏符号：敌人在下一个补给阶段不准备。"""
        state, bus, inv, enemy, impl = setup
        _play(state, bus)
        enemy.exhausted = True
        state.locations["loc2"].enemies.append("enemy_1")
        _evade_flow(state, bus, token=ChaosTokenType.TABLET)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.ENEMY_EVADED,
            investigator_id="inv1", enemy_id="enemy_1",
        ))
        # 补给阶段：引擎先就绪（emit CARD_READIED），本卡重新横置
        bus.emit(EventContext(
            game_state=state, event=GameEvent.UPKEEP_PHASE_BEGINS,
        ))
        enemy.exhausted = False
        rctx = EventContext(
            game_state=state, event=GameEvent.CARD_READIED,
            target="enemy_1",
        )
        bus.emit(rctx)
        assert enemy.exhausted is True
        assert rctx.extra["banish_prevented_ready"] is True

    def test_no_bad_token_readies_normally(self, setup):
        state, bus, inv, enemy, impl = setup
        _play(state, bus)
        enemy.exhausted = True
        _evade_flow(state, bus, token=ChaosTokenType.ZERO)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.ENEMY_EVADED,
            investigator_id="inv1", enemy_id="enemy_1",
        ))
        bus.emit(EventContext(
            game_state=state, event=GameEvent.UPKEEP_PHASE_BEGINS,
        ))
        enemy.exhausted = False
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_READIED,
            target="enemy_1",
        ))
        assert enemy.exhausted is False

    def test_elite_target_no_effect(self, setup):
        """精英敌人：本卡无效（不替换技能值）。"""
        state, bus, inv, enemy, impl = setup
        elite = make_enemy_data(id="elite_enemy")
        elite.keywords = ["elite"]
        state.card_database["elite_enemy"] = elite
        elite_inst = CardInstance(
            instance_id="enemy_elite", card_id="elite_enemy",
            owner_id="scenario", controller_id="scenario",
        )
        state.cards_in_play["enemy_elite"] = elite_inst

        _play(state, bus)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.EVADE_ACTION_INITIATED,
            investigator_id="inv1", enemy_id="enemy_elite",
        ))
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.AGILITY, amount=2,
        )
        bus.emit(ctx)
        assert ctx.amount == 2
