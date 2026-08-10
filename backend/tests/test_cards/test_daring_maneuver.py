"""Tests for Daring Maneuver (Level 0)."""

import pytest
from backend.cards.rogue.daring_maneuver_lv0 import DaringManeuver
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_event_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    state.card_database["daring_maneuver_lv0"] = make_event_data(
        id="daring_maneuver_lv0", cost=0, fast=True,
    )

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        hand=["daring_maneuver_lv0"], resources=3,
    )
    state.investigators["inv1"] = inv

    impl = DaringManeuver("dm_inst")
    impl.register(bus, "dm_inst")
    return state, bus, inv, impl


def _success_ctx(state, modified_skill=3, difficulty=2, success=True):
    event = GameEvent.SKILL_TEST_SUCCESSFUL if success else GameEvent.SKILL_TEST_FAILED
    return EventContext(
        game_state=state, event=event,
        investigator_id="inv1", skill_type=Skill.AGILITY, success=success,
        modified_skill=modified_skill, difficulty=difficulty,
    )


class TestDaringManeuver:
    def test_card_id(self):
        assert DaringManeuver.card_id == "daring_maneuver_lv0"

    def test_auto_play_on_success_boosts_skill(self, setup):
        """When you would succeed: auto-play from hand, +2 skill value."""
        state, bus, inv, impl = setup
        ctx = _success_ctx(state, modified_skill=3, difficulty=2)
        bus.emit(ctx)

        assert "daring_maneuver_lv0" not in inv.hand
        assert "daring_maneuver_lv0" in inv.discard
        assert ctx.modified_skill == 5
        assert ctx.extra["daring_maneuver_boost"] is True

    def test_boosted_margin_visible_to_later_handlers(self, setup):
        """Margin-based effects registered later see the boosted value."""
        state, bus, inv, impl = setup
        from backend.models.enums import TimingPriority
        seen = {}
        bus.register(
            GameEvent.SKILL_TEST_SUCCESSFUL,
            lambda ctx: seen.setdefault(
                "margin", (ctx.modified_skill or 0) - (ctx.difficulty or 0)),
            priority=TimingPriority.AFTER,
        )
        bus.emit(_success_ctx(state, modified_skill=3, difficulty=2))
        assert seen["margin"] == 3  # 1 base margin + 2 boost

    def test_no_trigger_on_failure(self, setup):
        state, bus, inv, impl = setup
        ctx = _success_ctx(state, modified_skill=1, difficulty=2, success=False)
        bus.emit(ctx)
        assert "daring_maneuver_lv0" in inv.hand
        assert ctx.modified_skill == 1

    def test_no_trigger_without_card_in_hand(self, setup):
        state, bus, inv, impl = setup
        inv.hand.remove("daring_maneuver_lv0")
        ctx = _success_ctx(state)
        bus.emit(ctx)
        assert ctx.modified_skill == 3
