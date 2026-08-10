"""Tests for Lockpicks (Level 1)."""

import pytest
from backend.cards.rogue.lockpicks_lv1 import Lockpicks
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

    inv_data = make_investigator_data(intellect=3, agility=4)
    state.card_database[inv_data.id] = inv_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
    )
    state.investigators["inv1"] = inv

    impl = Lockpicks("lp_inst")
    impl.register(bus, "lp_inst")

    ci = CardInstance(
        instance_id="lp_inst", card_id="lockpicks_lv1",
        owner_id="inv1", controller_id="inv1",
        uses={"supplies": 3},
    )
    state.cards_in_play["lp_inst"] = ci
    inv.play_area.append("lp_inst")
    return state, bus, inv, impl, ci


def _value_ctx(state, skill=Skill.INTELLECT, amount=3):
    return EventContext(
        game_state=state,
        event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1",
        skill_type=skill,
        amount=amount,
    )


def _success_ctx(state, modified_skill, difficulty):
    return EventContext(
        game_state=state,
        event=GameEvent.SKILL_TEST_SUCCESSFUL,
        investigator_id="inv1",
        skill_type=Skill.INTELLECT,
        success=True,
        modified_skill=modified_skill,
        difficulty=difficulty,
    )


class TestLockpicks:
    def test_card_id(self):
        """Lockpicks has correct card_id."""
        assert Lockpicks.card_id == "lockpicks_lv1"

    def test_activate_exhausts_without_spending_supply(self, setup):
        """Activation only exhausts; no supply is spent up front."""
        state, bus, inv, impl, ci = setup
        assert impl.activate(state, "inv1") is True
        assert ci.exhausted is True
        assert ci.uses["supplies"] == 3

    def test_activate_fails_when_exhausted(self, setup):
        state, bus, inv, impl, ci = setup
        ci.exhausted = True
        assert impl.activate(state, "inv1") is False

    def test_adds_agility_to_skill_value(self, setup):
        """Investigation adds agility value to the skill value."""
        state, bus, inv, impl, ci = setup
        impl.activate(state, "inv1")

        ctx = _value_ctx(state)
        bus.emit(ctx)
        assert ctx.amount == 3 + 4  # intellect base + agility value

    def test_no_bonus_when_not_armed(self, setup):
        state, bus, inv, impl, ci = setup
        ctx = _value_ctx(state)
        bus.emit(ctx)
        assert ctx.amount == 3

    def test_supply_kept_on_success_by_2(self, setup):
        """Succeed by at least 2: no supply removed."""
        state, bus, inv, impl, ci = setup
        impl.activate(state, "inv1")

        bus.emit(_success_ctx(state, modified_skill=5, difficulty=3))
        assert ci.uses["supplies"] == 3

    def test_supply_removed_on_low_margin_success(self, setup):
        """Succeed by less than 2: remove 1 supply."""
        state, bus, inv, impl, ci = setup
        impl.activate(state, "inv1")

        bus.emit(_success_ctx(state, modified_skill=4, difficulty=3))
        assert ci.uses["supplies"] == 2

    def test_supply_removed_on_failure(self, setup):
        state, bus, inv, impl, ci = setup
        impl.activate(state, "inv1")

        bus.emit(EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_FAILED,
            investigator_id="inv1",
            skill_type=Skill.INTELLECT,
            success=False,
        ))
        assert ci.uses["supplies"] == 2

    def test_discarded_when_supplies_run_out(self, setup):
        """No supplies left: Lockpicks is discarded."""
        state, bus, inv, impl, ci = setup
        ci.uses["supplies"] = 1
        impl.activate(state, "inv1")

        ctx = EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_FAILED,
            investigator_id="inv1",
            skill_type=Skill.INTELLECT,
            success=False,
        )
        bus.emit(ctx)
        assert "lp_inst" not in inv.play_area
        assert "lp_inst" not in state.cards_in_play
        assert "lockpicks_lv1" in inv.discard
        assert ctx.extra["lockpicks_discarded"] is True
