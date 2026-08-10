"""Tests for Stealth (Level 0)."""

import pytest
from backend.cards.rogue.stealth_lv0 import Stealth
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(agility=4)
    state.card_database[inv_data.id] = inv_data
    state.card_database["ghoul"] = make_enemy_data(id="ghoul", evade=3)

    loc_data = make_location_data(id="loc1")
    state.card_database["loc1"] = loc_data
    loc = LocationState(location_id="loc1", card_data=loc_data, revealed=True)
    state.locations["loc1"] = loc

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv

    enemy = CardInstance(
        instance_id="enemy_1", card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    state.cards_in_play["enemy_1"] = enemy
    inv.threat_area.append("enemy_1")

    ci = CardInstance(
        instance_id="stealth_inst", card_id="stealth_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["stealth_inst"] = ci
    inv.play_area.append("stealth_inst")

    impl = Stealth("stealth_inst")
    impl.register(bus, "stealth_inst")
    return state, bus, inv, impl, ci


def _evade_success(bus, state):
    """Simulate the engine's successful evade of enemy_1, then ENEMY_EVADED."""
    inv = state.investigators["inv1"]
    enemy = state.cards_in_play["enemy_1"]
    enemy.exhausted = True  # engine exhausts on successful evade
    if "enemy_1" in inv.threat_area:
        inv.threat_area.remove("enemy_1")
    loc = state.locations["loc1"]
    if "enemy_1" not in loc.enemies:
        loc.enemies.append("enemy_1")
    ctx = EventContext(
        game_state=state, event=GameEvent.ENEMY_EVADED,
        investigator_id="inv1", enemy_id="enemy_1",
    )
    bus.emit(ctx)
    return ctx


class TestStealth:
    def test_card_id(self):
        assert Stealth.card_id == "stealth_lv0"

    def test_activate_exhausts_and_arms(self, setup):
        state, bus, inv, impl, ci = setup
        assert impl.activate(state, "inv1") is True
        assert ci.exhausted is True

    def test_lowers_difficulty_by_2(self, setup):
        """The chosen enemy gets -2 evade for this evasion attempt."""
        state, bus, inv, impl, ci = setup
        impl.activate(state, "inv1")
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_BEGINS,
            investigator_id="inv1", skill_type=Skill.AGILITY, difficulty=3,
        )
        bus.emit(ctx)
        assert ctx.difficulty == 1
        assert ctx.extra["stealth_lowered"] is True

    def test_no_lower_when_not_armed(self, setup):
        state, bus, inv, impl, ci = setup
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_BEGINS,
            investigator_id="inv1", skill_type=Skill.AGILITY, difficulty=3,
        )
        bus.emit(ctx)
        assert ctx.difficulty == 3

    def test_successful_evade_does_not_exhaust(self, setup):
        """Successful evasion: disengage but do NOT exhaust the enemy."""
        state, bus, inv, impl, ci = setup
        impl.activate(state, "inv1")
        ctx = _evade_success(bus, state)

        enemy = state.cards_in_play["enemy_1"]
        assert enemy.exhausted is False
        assert "enemy_1" not in inv.threat_area
        assert "enemy_1" in state.locations["loc1"].enemies
        assert ctx.extra["stealth_no_exhaust"] == "enemy_1"

    def test_enemy_cannot_engage_you_this_turn(self, setup):
        """Until end of your turn, that enemy cannot engage you."""
        state, bus, inv, impl, ci = setup
        impl.activate(state, "inv1")
        _evade_success(bus, state)

        # Enemy tries to engage you again (e.g. hunter movement)
        loc = state.locations["loc1"]
        loc.enemies.remove("enemy_1")
        inv.threat_area.append("enemy_1")
        ctx = EventContext(
            game_state=state, event=GameEvent.ENEMY_ENGAGED,
            investigator_id="inv1", enemy_id="enemy_1",
        )
        bus.emit(ctx)

        assert "enemy_1" not in inv.threat_area
        assert "enemy_1" in loc.enemies
        assert ctx.extra["stealth_engagement_prevented"] == "enemy_1"

    def test_engagement_block_expires_at_turn_end(self, setup):
        state, bus, inv, impl, ci = setup
        impl.activate(state, "inv1")
        _evade_success(bus, state)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="inv1",
        ))

        loc = state.locations["loc1"]
        loc.enemies.remove("enemy_1")
        inv.threat_area.append("enemy_1")
        bus.emit(EventContext(
            game_state=state, event=GameEvent.ENEMY_ENGAGED,
            investigator_id="inv1", enemy_id="enemy_1",
        ))
        assert "enemy_1" in inv.threat_area  # engagement stands next turn
