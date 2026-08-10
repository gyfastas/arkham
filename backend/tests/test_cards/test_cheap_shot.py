"""Tests for Cheap Shot (Level 0)."""

import pytest
from backend.cards.rogue.cheap_shot_lv0 import CheapShot
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(combat=3, agility=4)
    state.card_database[inv_data.id] = inv_data
    state.card_database["cheap_shot_lv0"] = make_event_data(id="cheap_shot_lv0", cost=2)

    enemy_data = make_enemy_data(id="ghoul", fight=3)
    state.card_database["ghoul"] = enemy_data

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

    impl = CheapShot("cs_inst")
    impl.register(bus, "cs_inst")
    return state, bus, inv, impl


def _play(bus, state):
    ctx = EventContext(
        game_state=state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1", extra={"card_id": "cheap_shot_lv0"},
    )
    bus.emit(ctx)
    return ctx


def _fight(bus, state):
    bus.emit(EventContext(
        game_state=state, event=GameEvent.FIGHT_ACTION_INITIATED,
        investigator_id="inv1", enemy_id="enemy_1",
    ))


def _value_ctx(state, amount=3):
    return EventContext(
        game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1", skill_type=Skill.COMBAT, amount=amount,
    )


def _success(bus, state, modified_skill, difficulty):
    ctx = EventContext(
        game_state=state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
        investigator_id="inv1", skill_type=Skill.COMBAT, success=True,
        modified_skill=modified_skill, difficulty=difficulty,
    )
    bus.emit(ctx)
    return ctx


class TestCheapShot:
    def test_card_id(self):
        assert CheapShot.card_id == "cheap_shot_lv0"

    def test_adds_agility_when_armed(self, setup):
        """Fight: add your agility to your skill value for this attack."""
        state, bus, inv, impl = setup
        _play(bus, state)
        _fight(bus, state)

        ctx = _value_ctx(state, amount=3)
        bus.emit(ctx)
        assert ctx.amount == 3 + 4  # combat base + agility

    def test_no_bonus_without_play(self, setup):
        state, bus, inv, impl = setup
        ctx = _value_ctx(state, amount=3)
        bus.emit(ctx)
        assert ctx.amount == 3

    def test_auto_evade_on_margin_2(self, setup):
        """Succeed by 2+: automatically evade the attacked enemy."""
        state, bus, inv, impl = setup
        evaded = []
        bus.register(
            GameEvent.ENEMY_EVADED,
            lambda ctx: evaded.append(ctx.enemy_id),
        )
        _play(bus, state)
        _fight(bus, state)
        ctx = _success(bus, state, modified_skill=5, difficulty=3)

        enemy = state.cards_in_play["enemy_1"]
        assert enemy.exhausted is True
        assert "enemy_1" not in inv.threat_area
        assert "enemy_1" in state.locations["loc1"].enemies
        assert ctx.extra["cheap_shot_auto_evade"] == "enemy_1"
        assert evaded == ["enemy_1"]  # ENEMY_EVADED emitted

    def test_no_evade_below_margin_2(self, setup):
        state, bus, inv, impl = setup
        _play(bus, state)
        _fight(bus, state)
        _success(bus, state, modified_skill=4, difficulty=3)

        enemy = state.cards_in_play["enemy_1"]
        assert enemy.exhausted is False
        assert "enemy_1" in inv.threat_area

    def test_armed_state_cleared_after_test(self, setup):
        state, bus, inv, impl = setup
        _play(bus, state)
        _fight(bus, state)
        _success(bus, state, modified_skill=5, difficulty=3)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1",
        ))

        # A subsequent unrelated combat test gets no agility bonus
        ctx = _value_ctx(state, amount=3)
        bus.emit(ctx)
        assert ctx.amount == 3
