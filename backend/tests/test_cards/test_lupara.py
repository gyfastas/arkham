"""Tests for Lupara (Level 3)."""

import pytest
from backend.cards.rogue.lupara_lv3 import Lupara
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import Action, GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import (
    make_investigator_data, make_location_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(combat=3)
    state.card_database[inv_data.id] = inv_data

    loc_data = make_location_data(id="loc1")
    state.card_database["loc1"] = loc_data
    state.locations["loc1"] = LocationState(
        location_id="loc1", card_data=loc_data, revealed=True,
    )

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv

    weapon = CardInstance(
        instance_id="lupara_inst", card_id="lupara_lv3",
        owner_id="inv1", controller_id="inv1", uses={"ammo": 2},
    )
    state.cards_in_play["lupara_inst"] = weapon
    inv.play_area.append("lupara_inst")

    impl = Lupara("lupara_inst")
    impl.register(bus, "lupara_inst")
    return state, bus, inv, impl, weapon


def _enters_play(bus, state):
    bus.emit(EventContext(
        game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
        investigator_id="inv1", target="lupara_inst",
        extra={"card_id": "lupara_lv3"},
    ))


def _fight(bus, state):
    ctx = EventContext(
        game_state=state, event=GameEvent.FIGHT_ACTION_INITIATED,
        investigator_id="inv1", enemy_id="enemy_1", source="lupara_inst",
    )
    bus.emit(ctx)
    return ctx


def _value_ctx(state, amount=3):
    return EventContext(
        game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1", skill_type=Skill.COMBAT, amount=amount,
        source="lupara_inst",
    )


def _success(bus, state):
    ctx = EventContext(
        game_state=state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
        investigator_id="inv1", skill_type=Skill.COMBAT, success=True,
        modified_skill=5, difficulty=3, source="lupara_inst",
    )
    bus.emit(ctx)
    return ctx


class TestLupara:
    def test_card_id(self):
        assert Lupara.card_id == "lupara_lv3"

    def test_fight_spends_ammo(self, setup):
        state, bus, inv, impl, weapon = setup
        ctx = _fight(bus, state)
        assert ctx.cancelled is False
        assert weapon.uses["ammo"] == 1

    def test_no_ammo_cancels_attack(self, setup):
        state, bus, inv, impl, weapon = setup
        weapon.uses["ammo"] = 0
        ctx = _fight(bus, state)
        assert ctx.cancelled is True

    def test_base_bonus_is_plus_1_plus_1(self, setup):
        """+1 combat and +1 damage (not entered this turn)."""
        state, bus, inv, impl, weapon = setup
        _fight(bus, state)
        ctx = _value_ctx(state, amount=3)
        bus.emit(ctx)
        assert ctx.amount == 4
        ctx2 = _success(bus, state)
        assert ctx2.extra["bonus_damage"] == 1

    def test_entered_this_turn_double_bonus(self, setup):
        """Entered play this turn: +2 combat and +2 damage instead."""
        state, bus, inv, impl, weapon = setup
        _enters_play(bus, state)
        _fight(bus, state)
        ctx = _value_ctx(state, amount=3)
        bus.emit(ctx)
        assert ctx.amount == 5
        ctx2 = _success(bus, state)
        assert ctx2.extra["bonus_damage"] == 2

    def test_entered_flag_expires_at_turn_end(self, setup):
        state, bus, inv, impl, weapon = setup
        _enters_play(bus, state)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="inv1",
        ))
        _fight(bus, state)
        ctx = _value_ctx(state, amount=3)
        bus.emit(ctx)
        assert ctx.amount == 4

    def test_playing_provokes_no_aoo(self, setup):
        """Playing Lupara does not provoke attacks of opportunity."""
        state, bus, inv, impl, weapon = setup
        _enters_play(bus, state)
        ctx = EventContext(
            game_state=state, event=GameEvent.ATTACK_OF_OPPORTUNITY,
            investigator_id="inv1", enemy_id="enemy_1",
        )
        bus.emit(ctx)
        assert ctx.cancelled is True

    def test_aoo_window_closes_after_action(self, setup):
        state, bus, inv, impl, weapon = setup
        _enters_play(bus, state)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.ACTION_PERFORMED,
            investigator_id="inv1", action=Action.PLAY,
        ))
        ctx = EventContext(
            game_state=state, event=GameEvent.ATTACK_OF_OPPORTUNITY,
            investigator_id="inv1", enemy_id="enemy_1",
        )
        bus.emit(ctx)
        assert ctx.cancelled is False
