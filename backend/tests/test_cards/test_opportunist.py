"""Tests for Opportunist (Level 0)."""

import pytest
from backend.cards.rogue.opportunist_lv0 import Opportunist
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import GameState, InvestigatorState, ScenarioState
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
        hand=["opportunist_lv0"],
    )
    state.investigators["inv1"] = inv

    impl = Opportunist("opp_inst")
    impl.register(bus, "opp_inst")
    return state, bus, inv, impl


def _run_test(bus, state, inv, modified_skill, difficulty):
    """Simulate ST.6 success + ST.8 discard + SKILL_TEST_ENDS."""
    bus.emit(EventContext(
        game_state=state,
        event=GameEvent.SKILL_TEST_SUCCESSFUL,
        investigator_id="inv1",
        skill_type=Skill.AGILITY,
        success=True,
        modified_skill=modified_skill,
        difficulty=difficulty,
        committed_cards=["opportunist_lv0"],
    ))
    # Engine ST.8: committed cards are discarded before SKILL_TEST_ENDS
    if "opportunist_lv0" in inv.hand:
        inv.hand.remove("opportunist_lv0")
        inv.discard.append("opportunist_lv0")
    bus.emit(EventContext(
        game_state=state,
        event=GameEvent.SKILL_TEST_ENDS,
        investigator_id="inv1",
        success=True,
    ))


class TestOpportunist:
    def test_card_id(self):
        """Opportunist has correct card_id."""
        assert Opportunist.card_id == "opportunist_lv0"

    def test_returns_on_success_by_3(self, setup):
        """Succeed by 3 or more: return to hand instead of discarding."""
        state, bus, inv, impl = setup
        _run_test(bus, state, inv, modified_skill=6, difficulty=3)
        assert "opportunist_lv0" in inv.hand
        assert "opportunist_lv0" not in inv.discard

    def test_no_return_below_margin_3(self, setup):
        """Succeed by only 2: stays in the discard pile."""
        state, bus, inv, impl = setup
        _run_test(bus, state, inv, modified_skill=5, difficulty=3)
        assert "opportunist_lv0" in inv.discard
        assert "opportunist_lv0" not in inv.hand

    def test_no_return_on_failure(self, setup):
        """Failed test: stays in the discard pile."""
        state, bus, inv, impl = setup
        bus.emit(EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_FAILED,
            investigator_id="inv1",
            skill_type=Skill.AGILITY,
            success=False,
            committed_cards=["opportunist_lv0"],
        ))
        inv.hand.remove("opportunist_lv0")
        inv.discard.append("opportunist_lv0")
        bus.emit(EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1",
            success=False,
        ))
        assert "opportunist_lv0" in inv.discard
        assert "opportunist_lv0" not in inv.hand
