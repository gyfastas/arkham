"""Tests for Switchblade (Level 0)."""

import pytest
from backend.cards.rogue.switchblade_lv0 import Switchblade
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

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
    )
    state.investigators["inv1"] = inv

    impl = Switchblade("switchblade_inst")
    impl.register(bus, "switchblade_inst")

    ci = CardInstance(
        instance_id="switchblade_inst", card_id="switchblade_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["switchblade_inst"] = ci
    inv.play_area.append("switchblade_inst")
    return state, bus, inv, impl


def _success_ctx(state, modified_skill, difficulty, source="switchblade_inst"):
    return EventContext(
        game_state=state,
        event=GameEvent.SKILL_TEST_SUCCESSFUL,
        investigator_id="inv1",
        skill_type=Skill.COMBAT,
        success=True,
        modified_skill=modified_skill,
        difficulty=difficulty,
        source=source,
    )


class TestSwitchblade:
    def test_card_id(self, setup):
        """Switchblade has correct card_id."""
        assert Switchblade.card_id == "switchblade_lv0"

    def test_no_combat_bonus(self, setup):
        """Official text grants no +1 combat."""
        state, bus, inv, impl = setup
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            amount=3,
            source="switchblade_inst",
            extra={"weapon_card_id": "switchblade_lv0"},
        )
        bus.emit(ctx)
        assert ctx.amount == 3

    def test_bonus_damage_at_margin_2(self, setup):
        """Succeed by 2 or more: +1 damage."""
        state, bus, inv, impl = setup
        ctx = _success_ctx(state, modified_skill=5, difficulty=3)
        bus.emit(ctx)
        assert ctx.extra["bonus_damage"] == 1

    def test_no_bonus_damage_below_margin_2(self, setup):
        """Plain success: no bonus damage."""
        state, bus, inv, impl = setup
        ctx = _success_ctx(state, modified_skill=4, difficulty=3)
        bus.emit(ctx)
        assert "bonus_damage" not in ctx.extra

    def test_no_effect_for_other_weapon(self, setup):
        state, bus, inv, impl = setup
        ctx = _success_ctx(state, modified_skill=6, difficulty=3, source="other_weapon")
        bus.emit(ctx)
        assert "bonus_damage" not in ctx.extra
