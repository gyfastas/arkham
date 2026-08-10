"""Tests for Breaking and Entering (Level 0)."""

import pytest
from backend.cards.rogue.breaking_and_entering_lv0 import BreakingAndEntering
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
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
    inv_data = make_investigator_data(intellect=3, agility=4)
    state.card_database[inv_data.id] = inv_data
    loc_data = make_location_data(id="loc1")
    state.card_database["loc1"] = loc_data
    state.locations["loc1"] = LocationState(
        location_id="loc1", card_data=loc_data, clues=2, revealed=True,
    )
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv

    enemy_data = make_enemy_data()
    state.card_database["test_enemy"] = enemy_data
    state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    inv.threat_area.append("enemy_1")

    impl = BreakingAndEntering("bae_inst")
    impl.register(bus, "bae_inst")
    return state, bus, inv, impl


def _play(bus, state):
    bus.emit(EventContext(
        game_state=state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1", extra={"card_id": "breaking_and_entering_lv0"},
    ))


class TestBreakingAndEntering:
    def test_agility_added_to_intellect(self, setup):
        """本次调查：敏捷值(4)加入技能值 → 3+4=7。"""
        state, bus, inv, impl = setup
        _play(bus, state)
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.INTELLECT, amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 7

    def test_auto_evade_on_margin_2(self, setup):
        """成功超2：自动躲避此地点一名敌人（横置、解除交战、发事件）。"""
        state, bus, inv, impl = setup
        _play(bus, state)
        evaded = []
        bus.register(
            event=GameEvent.ENEMY_EVADED,
            handler=lambda c: evaded.append(c.enemy_id),
        )
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1", skill_type=Skill.INTELLECT,
            success=True, modified_skill=6, difficulty=4,
        )
        bus.emit(ctx)
        enemy = state.get_card_instance("enemy_1")
        assert enemy.exhausted is True
        assert "enemy_1" not in inv.threat_area
        assert "enemy_1" in state.locations["loc1"].enemies
        assert evaded == ["enemy_1"]

    def test_no_evade_below_margin_2(self, setup):
        state, bus, inv, impl = setup
        _play(bus, state)
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1", skill_type=Skill.INTELLECT,
            success=True, modified_skill=5, difficulty=4,
        )
        bus.emit(ctx)
        assert state.get_card_instance("enemy_1").exhausted is False
        assert "enemy_1" in inv.threat_area

    def test_aoo_cancelled_for_the_investigate(self, setup):
        """该调查行动不引起趁乱攻击。"""
        state, bus, inv, impl = setup
        _play(bus, state)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.INVESTIGATE_ACTION_INITIATED,
            investigator_id="inv1", location_id="loc1",
        ))
        ctx = EventContext(
            game_state=state, event=GameEvent.ATTACK_OF_OPPORTUNITY,
            investigator_id="inv1", enemy_id="enemy_1",
        )
        bus.emit(ctx)
        assert ctx.cancelled is True

    def test_no_effect_when_not_played(self, setup):
        state, bus, inv, impl = setup
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.INTELLECT, amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 3
