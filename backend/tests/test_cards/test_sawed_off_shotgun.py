"""Tests for Sawed-Off Shotgun (Level 5)."""

import pytest

from backend.cards.rogue.sawed_off_shotgun_lv5 import SawedOffShotgun
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data(combat=5)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    state.investigators["inv1"] = inv
    inst = CardInstance(
        instance_id="shotgun_inst", card_id="sawed_off_shotgun_lv5",
        owner_id="inv1", controller_id="inv1", uses={"ammo": 2},
    )
    state.cards_in_play["shotgun_inst"] = inst
    inv.play_area.append("shotgun_inst")
    impl = SawedOffShotgun("shotgun_inst")
    impl.register(bus, "shotgun_inst")
    return state, bus, inv, inst


def _initiate(bus, state):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.FIGHT_ACTION_INITIATED,
        investigator_id="inv1",
        enemy_id="enemy_1",
        source="shotgun_inst",
    )
    bus.emit(ctx)
    return ctx


def _success(bus, state, modified, difficulty):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.SKILL_TEST_SUCCESSFUL,
        investigator_id="inv1",
        skill_type=Skill.COMBAT,
        success=True,
        modified_skill=modified,
        difficulty=difficulty,
        source="shotgun_inst",
    )
    bus.emit(ctx)
    return ctx


class TestSawedOffShotgun:
    def test_ammo_spent_on_initiate(self, setup):
        state, bus, inv, inst = setup
        _initiate(bus, state)
        assert inst.uses["ammo"] == 1

    def test_no_ammo_cancels_attack(self, setup):
        state, bus, inv, inst = setup
        inst.uses["ammo"] = 0
        ctx = _initiate(bus, state)
        assert ctx.cancelled is True

    def test_damage_equals_margin(self, setup):
        """Succeed by 4 → 4 damage (base 1 replaced: bonus_damage = 3)."""
        state, bus, inv, inst = setup
        _initiate(bus, state)
        ctx = _success(bus, state, modified=7, difficulty=3)
        assert ctx.extra["sawed_off_damage"] == 4
        assert ctx.extra["bonus_damage"] == 3

    def test_minimum_one_damage(self, setup):
        """Succeed by 0 → still 1 damage (bonus_damage = 0)."""
        state, bus, inv, inst = setup
        _initiate(bus, state)
        ctx = _success(bus, state, modified=3, difficulty=3)
        assert ctx.extra["sawed_off_damage"] == 1
        assert ctx.extra["bonus_damage"] == 0

    def test_maximum_six_damage(self, setup):
        """Succeed by 9 → capped at 6 damage (bonus_damage = 5)."""
        state, bus, inv, inst = setup
        _initiate(bus, state)
        ctx = _success(bus, state, modified=12, difficulty=3)
        assert ctx.extra["sawed_off_damage"] == 6
        assert ctx.extra["bonus_damage"] == 5

    def test_fail_margin_recorded(self, setup):
        state, bus, inv, inst = setup
        _initiate(bus, state)
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_FAILED,
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            success=False,
            modified_skill=1,
            difficulty=3,
            source="shotgun_inst",
        )
        bus.emit(ctx)
        assert ctx.extra["sawed_off_fail_damage"] == 2

    def test_other_weapon_untouched(self, setup):
        state, bus, inv, inst = setup
        _initiate(bus, state)
        ctx = _success(bus, state, modified=7, difficulty=3)
        ctx.source = "machete_inst"
        ctx2 = EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            success=True,
            modified_skill=7,
            difficulty=3,
            source="machete_inst",
        )
        bus.emit(ctx2)
        assert "bonus_damage" not in ctx2.extra
