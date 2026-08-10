"""Tests for Pickpocketing (Level 2)."""

import pytest
from backend.cards.rogue.pickpocketing_lv2 import PickpocketingLv2
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(agility=4)
    state.card_database[inv_data.id] = inv_data
    state.card_database["pickpocketing_lv2"] = make_asset_data(
        id="pickpocketing_lv2", cost=2,
    )

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        deck=["card_a", "card_b"], resources=1,
    )
    state.investigators["inv1"] = inv

    ci = CardInstance(
        instance_id="pp_inst", card_id="pickpocketing_lv2",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["pp_inst"] = ci
    inv.play_area.append("pp_inst")

    impl = PickpocketingLv2("pp_inst")
    impl.register(bus, "pp_inst")
    return state, bus, inv, impl, ci


def _evade(bus, state, modified_skill=None, difficulty=None):
    if modified_skill is not None:
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1", skill_type=Skill.AGILITY, success=True,
            modified_skill=modified_skill, difficulty=difficulty,
        ))
    ctx = EventContext(
        game_state=state, event=GameEvent.ENEMY_EVADED,
        investigator_id="inv1", enemy_id="enemy_1",
    )
    bus.emit(ctx)
    return ctx


class TestPickpocketingLv2:
    def test_card_id(self):
        assert PickpocketingLv2.card_id == "pickpocketing_lv2"

    def test_default_draws_card(self, setup):
        """After you evade: exhaust to draw 1 card (default choice)."""
        state, bus, inv, impl, ci = setup
        ctx = _evade(bus, state, modified_skill=4, difficulty=3)

        assert ci.exhausted is True
        assert inv.hand == ["card_a"]
        assert inv.resources == 1
        assert ctx.extra["pickpocketing_lv2_draw"] is True

    def test_choice_resource(self, setup):
        """Preset choice: gain 1 resource instead of drawing."""
        state, bus, inv, impl, ci = setup
        assert impl.set_choice(state, "inv1", "resource") is True
        ctx = _evade(bus, state, modified_skill=4, difficulty=3)

        assert inv.hand == []
        assert inv.resources == 2
        assert ctx.extra["pickpocketing_lv2_resource"] is True

    def test_succeed_by_2_does_both(self, setup):
        """Succeed by 2+: draw 1 card AND gain 1 resource."""
        state, bus, inv, impl, ci = setup
        ctx = _evade(bus, state, modified_skill=5, difficulty=3)

        assert inv.hand == ["card_a"]
        assert inv.resources == 2
        assert ctx.extra["pickpocketing_lv2_draw"] is True
        assert ctx.extra["pickpocketing_lv2_resource"] is True

    def test_no_trigger_when_exhausted(self, setup):
        state, bus, inv, impl, ci = setup
        ci.exhausted = True
        _evade(bus, state, modified_skill=5, difficulty=3)
        assert inv.hand == []
        assert inv.resources == 1

    def test_margin_cleared_after_test(self, setup):
        """A stale high margin must not leak into a later evade."""
        state, bus, inv, impl, ci = setup
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1", skill_type=Skill.AGILITY, success=True,
            modified_skill=7, difficulty=3,
        ))
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1",
        ))
        # Evade without a fresh margin (e.g. auto-evade): default single choice
        ctx = _evade(bus, state)
        assert inv.hand == ["card_a"]
        assert inv.resources == 1  # not both
        assert "pickpocketing_lv2_resource" not in ctx.extra
