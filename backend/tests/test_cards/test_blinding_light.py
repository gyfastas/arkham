"""Tests for Blinding Light (Level 0). (01066)

躲避。本次躲避用意志代替敏捷；成功时对刚躲避的敌人造成1伤害；
揭示 skull/cultist/tablet/elder_thing/auto_fail 时本回合失去1行动。
"""

import pytest
from backend.cards.mystic.blinding_light_lv0 import BlindingLight
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(willpower=4, agility=2)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv

    state.card_database["blinding_light_lv0"] = make_event_data(
        id="blinding_light_lv0", name="Blinding Light",
    )
    state.card_database["test_enemy"] = make_enemy_data()
    enemy = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    state.cards_in_play["enemy_1"] = enemy

    impl = BlindingLight("inst_bl")
    impl.register(bus, "inst_bl")
    return state, bus, inv, enemy, impl


def _play(state, bus, card_id="blinding_light_lv0"):
    bus.emit(EventContext(
        game_state=state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1", extra={"card_id": card_id},
    ))


class TestBlindingLight:
    def test_willpower_substitute_no_bonus(self, setup):
        """意志(4)代替敏捷(2)，无额外加值。"""
        state, bus, inv, enemy, impl = setup
        _play(state, bus)
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.AGILITY, amount=2,
        )
        bus.emit(ctx)
        assert ctx.amount == 4

    def test_no_substitute_for_other_skills(self, setup):
        state, bus, inv, enemy, impl = setup
        _play(state, bus)
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.COMBAT, amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 3

    def test_damage_on_enemy_evaded(self, setup):
        """成功躲避：对刚躲避的敌人造成1伤害。"""
        state, bus, inv, enemy, impl = setup
        _play(state, bus)
        ctx = EventContext(
            game_state=state, event=GameEvent.ENEMY_EVADED,
            investigator_id="inv1", enemy_id="enemy_1",
        )
        bus.emit(ctx)
        assert enemy.damage == 1
        assert ctx.extra["blinding_light_lv0_damage"] == 1

    def test_no_damage_when_not_armed(self, setup):
        state, bus, inv, enemy, impl = setup
        bus.emit(EventContext(
            game_state=state, event=GameEvent.ENEMY_EVADED,
            investigator_id="inv1", enemy_id="enemy_1",
        ))
        assert enemy.damage == 0

    def test_bad_token_loses_one_action(self, setup):
        """揭示坏标记：检定结束时本回合失去1行动。"""
        state, bus, inv, enemy, impl = setup
        inv.actions_remaining = 3
        _play(state, bus)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.SKULL,
        ))
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1",
        ))
        assert inv.actions_remaining == 2

    def test_good_token_no_penalty_and_cleared(self, setup):
        """无坏标记：不失行动；武装状态在检定结束清除。"""
        state, bus, inv, enemy, impl = setup
        inv.actions_remaining = 3
        _play(state, bus)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1", chaos_token=ChaosTokenType.MINUS_1,
        ))
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1",
        ))
        assert inv.actions_remaining == 3
        # 武装已清除：后续躲避不再造成伤害
        bus.emit(EventContext(
            game_state=state, event=GameEvent.ENEMY_EVADED,
            investigator_id="inv1", enemy_id="enemy_1",
        ))
        assert enemy.damage == 0
