"""Tests for Savant (Level 1)."""

import pytest

from backend.cards.rogue.savant_lv1 import Savant
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data(willpower=4, intellect=2, combat=3, agility=2)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    state.investigators["inv1"] = inv
    impl = Savant("savant_inst")
    impl.register(bus, "savant_inst")
    return state, bus, inv


def _commit(bus, state, skill, cards=("savant_lv1",)):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.SKILL_TEST_COMMIT,
        investigator_id="inv1",
        skill_type=skill,
        difficulty=3,
        committed_cards=list(cards),
        amount=1,  # printed wild icon already counted by the engine
    )
    bus.emit(ctx)
    return ctx


class TestSavant:
    def test_intellect_test_gains_lowest_other(self, setup):
        """Intellect test: lowest of willpower 4 / combat 3 / agility 2 → +2."""
        state, bus, inv = setup
        ctx = _commit(bus, state, Skill.INTELLECT)
        assert ctx.amount == 3  # 1 printed + 2 gained
        assert ctx.extra["savant_icons"] == 2

    def test_agility_test_uses_other_skills(self, setup):
        """Agility test: lowest of willpower 4 / intellect 2 / combat 3 → +2."""
        state, bus, inv = setup
        ctx = _commit(bus, state, Skill.AGILITY)
        assert ctx.amount == 3

    def test_lowest_excludes_tested_skill(self, setup):
        """Willpower test: intellect 2 is lowest of the others → +2 (not 4)."""
        state, bus, inv = setup
        ctx = _commit(bus, state, Skill.WILLPOWER)
        assert ctx.amount == 3
        assert ctx.extra["savant_icons"] == 2

    def test_not_committed_no_bonus(self, setup):
        state, bus, inv = setup
        ctx = _commit(bus, state, Skill.INTELLECT, cards=("guts_lv0",))
        assert ctx.amount == 1
        assert "savant_icons" not in ctx.extra
