"""Tests for "Watch this!" (Level 0)."""

import pytest
from backend.cards.rogue.watch_this_lv0 import WatchThis
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_investigator_data, make_skill_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    state.card_database["watch_this_lv0"] = make_skill_data(
        id="watch_this_lv0",
        skill_icons={"willpower": 1, "combat": 1, "agility": 1},
    )

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        resources=5,
    )
    state.investigators["inv1"] = inv

    impl = WatchThis("wt_inst")
    impl.register(bus, "wt_inst")
    return state, bus, inv, impl


def _commit(bus, state):
    ctx = EventContext(
        game_state=state, event=GameEvent.SKILL_TEST_COMMIT,
        investigator_id="inv1", skill_type=Skill.COMBAT,
        difficulty=3, committed_cards=["watch_this_lv0"], amount=1,
    )
    bus.emit(ctx)
    return ctx


def _success(bus, state, modified_skill, difficulty):
    ctx = EventContext(
        game_state=state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
        investigator_id="inv1", skill_type=Skill.COMBAT, success=True,
        modified_skill=modified_skill, difficulty=difficulty,
    )
    bus.emit(ctx)
    return ctx


class TestWatchThis:
    def test_card_id(self):
        assert WatchThis.card_id == "watch_this_lv0"

    def test_commit_spends_up_to_3_resources(self, setup):
        """Additional cost to commit: spend up to 3 resources."""
        state, bus, inv, impl = setup
        ctx = _commit(bus, state)
        assert inv.resources == 2  # 5 - 3
        assert ctx.extra["watch_this_wager"] == 3

    def test_wager_capped_by_resources(self, setup):
        state, bus, inv, impl = setup
        inv.resources = 2
        _commit(bus, state)
        assert inv.resources == 0

    def test_success_by_1_gains_double(self, setup):
        """Succeed by 1+: gain twice the wagered resources."""
        state, bus, inv, impl = setup
        _commit(bus, state)
        ctx = _success(bus, state, modified_skill=4, difficulty=3)
        assert inv.resources == 2 + 6  # wager 3 → payout 6
        assert ctx.extra["watch_this_payout"] == 6

    def test_exact_success_margin_0_no_payout(self, setup):
        state, bus, inv, impl = setup
        _commit(bus, state)
        _success(bus, state, modified_skill=3, difficulty=3)
        assert inv.resources == 2  # no payout

    def test_no_wager_when_not_committed(self, setup):
        state, bus, inv, impl = setup
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_COMMIT,
            investigator_id="inv1", skill_type=Skill.COMBAT,
            difficulty=3, committed_cards=["guts_lv0"], amount=0,
        )
        bus.emit(ctx)
        assert inv.resources == 5
