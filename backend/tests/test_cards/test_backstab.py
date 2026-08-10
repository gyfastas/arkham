"""Tests for Backstab (Level 0)."""

import pytest
from backend.cards.rogue.backstab_lv0 import Backstab
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(combat=2, agility=4)
    state.card_database[inv_data.id] = inv_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
    )
    state.investigators["inv1"] = inv

    impl = Backstab("backstab_inst")
    impl.register(bus, "backstab_inst")
    return state, bus, inv, impl


def _play(bus, state):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "backstab_lv0"},
    )
    bus.emit(ctx)


class TestBackstab:
    def test_card_id(self, setup):
        """Backstab has correct card_id."""
        assert Backstab.card_id == "backstab_lv0"

    def test_agility_substitution_no_skill_bonus(self, setup):
        """Combat test uses agility instead of combat, with no +2 skill bonus."""
        state, bus, inv, impl = setup
        _play(bus, state)

        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            amount=inv.get_skill(Skill.COMBAT),
        )
        bus.emit(ctx)
        assert ctx.amount == 4  # agility 4 substituted for combat 2, no extra bonus

    def test_bonus_damage_plus_2_on_success(self, setup):
        """Successful attack deals +2 damage via the bonus_damage channel."""
        state, bus, inv, impl = setup
        _play(bus, state)

        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            success=True,
            modified_skill=5,
            difficulty=3,
        )
        bus.emit(ctx)
        assert ctx.extra["bonus_damage"] == 2

    def test_no_effect_when_not_armed(self, setup):
        """Without playing Backstab, no substitution or bonus damage."""
        state, bus, inv, impl = setup

        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            amount=2,
        )
        bus.emit(ctx)
        assert ctx.amount == 2

        ctx2 = EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            success=True,
            modified_skill=5,
            difficulty=3,
        )
        bus.emit(ctx2)
        assert "bonus_damage" not in ctx2.extra

    def test_effect_cleared_after_test(self, setup):
        """The armed effect is consumed when the skill test ends."""
        state, bus, inv, impl = setup
        _play(bus, state)

        bus.emit(EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1",
            success=True,
        ))

        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            amount=2,
        )
        bus.emit(ctx)
        assert ctx.amount == 2
