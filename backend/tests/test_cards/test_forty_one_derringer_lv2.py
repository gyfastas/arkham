"""Tests for .41 Derringer (Level 2)."""

import pytest
from backend.cards.rogue.forty_one_derringer_lv2 import FortyOneDerringerLv2
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

    impl = FortyOneDerringerLv2("d2_inst")
    impl.register(bus, "d2_inst")

    ci = CardInstance(
        instance_id="d2_inst", card_id="forty_one_derringer_lv2",
        owner_id="inv1", controller_id="inv1",
        uses={"ammo": 3},
    )
    state.cards_in_play["d2_inst"] = ci
    inv.play_area.append("d2_inst")
    return state, bus, inv, impl, ci


def _success_ctx(state, modified_skill, difficulty, source="d2_inst"):
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


class TestFortyOneDerringerLv2:
    def test_card_id(self):
        """.41 Derringer lv2 has correct card_id."""
        assert FortyOneDerringerLv2.card_id == "forty_one_derringer_lv2"

    def test_margin_damage_at_1_or_more(self, setup):
        """lv2: succeed by 1 or more deals +1 damage."""
        state, bus, inv, impl, ci = setup
        ctx = _success_ctx(state, modified_skill=4, difficulty=3)
        bus.emit(ctx)
        assert ctx.extra["bonus_damage"] == 1

    def test_extra_action_at_margin_3(self, setup):
        """Once per turn: succeed by 3 or more grants an additional action."""
        state, bus, inv, impl, ci = setup
        inv.actions_remaining = 1
        ctx = _success_ctx(state, modified_skill=6, difficulty=3)
        bus.emit(ctx)
        assert inv.actions_remaining == 2
        assert ctx.extra["forty_one_derringer_lv2_extra_action"] is True

    def test_extra_action_only_once_per_turn(self, setup):
        state, bus, inv, impl, ci = setup
        inv.actions_remaining = 0
        bus.emit(_success_ctx(state, modified_skill=6, difficulty=3))
        bus.emit(_success_ctx(state, modified_skill=7, difficulty=3))
        assert inv.actions_remaining == 1

    def test_extra_action_resets_next_turn(self, setup):
        state, bus, inv, impl, ci = setup
        inv.actions_remaining = 0
        bus.emit(_success_ctx(state, modified_skill=6, difficulty=3))
        assert inv.actions_remaining == 1

        bus.emit(EventContext(
            game_state=state,
            event=GameEvent.INVESTIGATOR_TURN_BEGINS,
            investigator_id="inv1",
        ))
        bus.emit(_success_ctx(state, modified_skill=6, difficulty=3))
        assert inv.actions_remaining == 2

    def test_no_extra_action_below_margin_3(self, setup):
        state, bus, inv, impl, ci = setup
        inv.actions_remaining = 0
        bus.emit(_success_ctx(state, modified_skill=5, difficulty=3))
        assert inv.actions_remaining == 0
