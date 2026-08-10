"""Tests for Double or Nothing (Level 0)."""

import pytest
from backend.cards.rogue.double_or_nothing_lv0 import DoubleOrNothing
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data

    loc_data = make_location_data(id="loc1")
    state.card_database["loc1"] = loc_data
    state.locations["loc1"] = LocationState(
        location_id="loc1", card_data=loc_data, clues=3, revealed=True,
    )

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
    )
    state.investigators["inv1"] = inv

    impl = DoubleOrNothing("don_inst")
    impl.register(bus, "don_inst")
    return state, bus, inv, impl


def _commit_ctx(state, difficulty):
    return EventContext(
        game_state=state,
        event=GameEvent.SKILL_TEST_COMMIT,
        investigator_id="inv1",
        skill_type=Skill.COMBAT,
        difficulty=difficulty,
        committed_cards=["double_or_nothing_lv0"],
        amount=1,
    )


class TestDoubleOrNothing:
    def test_card_id(self):
        assert DoubleOrNothing.card_id == "double_or_nothing_lv0"

    def test_difficulty_doubled(self, setup):
        """Committing doubles the test difficulty (engine reads ctx.difficulty back)."""
        state, bus, inv, impl = setup
        ctx = _commit_ctx(state, difficulty=2)
        bus.emit(ctx)
        assert ctx.difficulty == 4
        assert ctx.extra["double_or_nothing_doubled_difficulty"] == 4

    def test_combat_success_doubles_damage(self, setup):
        """Combat success resolves damage twice via the bonus_damage channel."""
        state, bus, inv, impl = setup
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            success=True,
            modified_skill=8,
            difficulty=4,
            committed_cards=["double_or_nothing_lv0"],
        )
        bus.emit(ctx)
        # bare-hand attack resolved twice: 2 x 1 → bonus_damage = 1
        assert ctx.extra["bonus_damage"] == 1
        assert ctx.extra["double_or_nothing"] is True

    def test_combat_double_stacks_with_existing_bonus(self, setup):
        """Existing bonus damage is part of the doubled attack."""
        state, bus, inv, impl = setup
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            success=True,
            modified_skill=8,
            difficulty=4,
            committed_cards=["double_or_nothing_lv0"],
            extra={"bonus_damage": 1},
        )
        bus.emit(ctx)
        # 2 x (1 base + 1 bonus) = 4 total → bonus_damage = 3
        assert ctx.extra["bonus_damage"] == 3

    def test_investigate_success_extra_clue(self, setup):
        """Investigate success discovers an extra clue."""
        state, bus, inv, impl = setup
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1",
            skill_type=Skill.INTELLECT,
            success=True,
            modified_skill=6,
            difficulty=2,
            committed_cards=["double_or_nothing_lv0"],
        )
        bus.emit(ctx)
        assert inv.clues == 1
        assert state.locations["loc1"].clues == 2

    def test_no_effect_when_not_committed(self, setup):
        state, bus, inv, impl = setup
        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            success=True,
            modified_skill=8,
            difficulty=4,
            committed_cards=[],
        )
        bus.emit(ctx)
        assert "bonus_damage" not in ctx.extra
        assert "double_or_nothing" not in ctx.extra
