"""Tests for Slip Away (Level 0)."""

import pytest

from backend.cards.rogue.slip_away_lv0 import SlipAway
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_enemy_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data(intellect=3, agility=4)
    state.card_database[inv_data.id] = inv_data
    enemy_data = make_enemy_data(id="thug", evade=3)
    state.card_database["thug"] = enemy_data
    elite_data = make_enemy_data(id="boss", evade=3, keywords=["elite"])
    state.card_database["boss"] = elite_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    state.investigators["inv1"] = inv
    state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="thug",
        owner_id="scenario", controller_id="scenario")
    state.cards_in_play["enemy_2"] = CardInstance(
        instance_id="enemy_2", card_id="boss",
        owner_id="scenario", controller_id="scenario")
    impl = SlipAway("slip_inst")
    impl.register(bus, "slip_inst")
    return state, bus, inv


def _play_and_evade(bus, state, enemy_id="enemy_1"):
    bus.emit(EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "slip_away_lv0"},
    ))
    bus.emit(EventContext(
        game_state=state,
        event=GameEvent.EVADE_ACTION_INITIATED,
        investigator_id="inv1",
        enemy_id=enemy_id,
    ))


class TestSlipAway:
    def test_intellect_added_to_agility(self, setup):
        state, bus, inv = setup
        _play_and_evade(bus, state)
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1",
            skill_type=Skill.AGILITY,
            amount=4,
        )
        bus.emit(ctx)
        assert ctx.amount == 7  # 4 agility + 3 intellect

    def test_succeed_by_two_enemy_skips_ready(self, setup):
        state, bus, inv = setup
        _play_and_evade(bus, state)
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1",
            skill_type=Skill.AGILITY,
            success=True,
            modified_skill=7,
            difficulty=3,
        )
        bus.emit(ctx)
        assert ctx.extra["slip_away_no_ready"] == "enemy_1"

        # 敌人被躲避后横置；补给阶段引擎就绪它并发出 CARD_READIED
        enemy = state.get_card_instance("enemy_1")
        enemy.exhausted = True
        enemy.exhausted = False  # 引擎 _ready_all 将就绪
        bus.emit(EventContext(
            game_state=state,
            event=GameEvent.CARD_READIED,
            target="enemy_1",
        ))
        assert enemy.exhausted is True  # 被重新横置

        # 仅抑制一次：下次就绪正常
        enemy.exhausted = False
        bus.emit(EventContext(
            game_state=state,
            event=GameEvent.CARD_READIED,
            target="enemy_1",
        ))
        assert enemy.exhausted is False

    def test_margin_one_no_suppression(self, setup):
        state, bus, inv = setup
        _play_and_evade(bus, state)
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1",
            skill_type=Skill.AGILITY,
            success=True,
            modified_skill=4,
            difficulty=3,
        )
        bus.emit(ctx)
        assert "slip_away_no_ready" not in ctx.extra

    def test_elite_enemy_no_suppression(self, setup):
        state, bus, inv = setup
        _play_and_evade(bus, state, enemy_id="enemy_2")
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1",
            skill_type=Skill.AGILITY,
            success=True,
            modified_skill=7,
            difficulty=3,
        )
        bus.emit(ctx)
        assert "slip_away_no_ready" not in ctx.extra

    def test_not_armed_no_bonus(self, setup):
        state, bus, inv = setup
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1",
            skill_type=Skill.AGILITY,
            amount=4,
        )
        bus.emit(ctx)
        assert ctx.amount == 4
