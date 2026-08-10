"""Tests for Suggestion (Level 4)."""

import pytest
from backend.cards.rogue.suggestion_lv4 import Suggestion
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

    inv_data = make_investigator_data(willpower=4, agility=3)
    state.card_database[inv_data.id] = inv_data
    state.card_database["ghoul"] = make_enemy_data(id="ghoul", evade=3)
    state.card_database["boss"] = make_enemy_data(
        id="boss", evade=4, keywords=["elite"],
    )

    loc_data = make_location_data(id="loc1")
    state.card_database["loc1"] = loc_data
    state.locations["loc1"] = LocationState(
        location_id="loc1", card_data=loc_data, revealed=True,
    )

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv

    ci = CardInstance(
        instance_id="sug_inst", card_id="suggestion_lv4",
        owner_id="inv1", controller_id="inv1", uses={"charges": 3},
    )
    state.cards_in_play["sug_inst"] = ci
    inv.play_area.append("sug_inst")

    impl = Suggestion("sug_inst")
    impl.register(bus, "sug_inst")
    return state, bus, inv, impl, ci


def _test_result(bus, state, success, modified_skill=4, difficulty=3):
    event = GameEvent.SKILL_TEST_SUCCESSFUL if success else GameEvent.SKILL_TEST_FAILED
    ctx = EventContext(
        game_state=state, event=event,
        investigator_id="inv1", skill_type=Skill.AGILITY, success=success,
        modified_skill=modified_skill, difficulty=difficulty,
    )
    bus.emit(ctx)
    return ctx


class TestSuggestion:
    def test_card_id(self):
        assert Suggestion.card_id == "suggestion_lv4"

    def test_activate_exhausts_and_arms(self, setup):
        state, bus, inv, impl, ci = setup
        assert impl.activate(state, "inv1") is True
        assert ci.exhausted is True
        assert ci.uses["charges"] == 3  # no charge spent up front

    def test_adds_willpower_to_evade(self, setup):
        """Evade: add your willpower to your skill value."""
        state, bus, inv, impl, ci = setup
        impl.activate(state, "inv1")
        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.AGILITY, amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 3 + 4  # agility base + willpower

    def test_charge_removed_below_margin_2(self, setup):
        state, bus, inv, impl, ci = setup
        impl.activate(state, "inv1")
        ctx = _test_result(bus, state, success=True, modified_skill=4, difficulty=3)
        assert ci.uses["charges"] == 2
        assert ctx.extra["suggestion_charge_removed"] is True

    def test_charge_kept_at_margin_2(self, setup):
        state, bus, inv, impl, ci = setup
        impl.activate(state, "inv1")
        _test_result(bus, state, success=True, modified_skill=5, difficulty=3)
        assert ci.uses["charges"] == 3

    def test_charge_removed_on_failure(self, setup):
        state, bus, inv, impl, ci = setup
        impl.activate(state, "inv1")
        _test_result(bus, state, success=False)
        assert ci.uses["charges"] == 2

    def test_no_discard_when_charges_empty(self, setup):
        """Official text has no discard clause: empty Suggestion stays in play."""
        state, bus, inv, impl, ci = setup
        ci.uses["charges"] = 1
        impl.activate(state, "inv1")
        _test_result(bus, state, success=False)
        assert ci.uses["charges"] == 0
        assert "sug_inst" in inv.play_area

    def test_reaction_cancels_non_elite_attack(self, setup):
        """Spend 1 charge: cancel a non-Elite enemy's attack on you."""
        state, bus, inv, impl, ci = setup
        state.cards_in_play["enemy_1"] = CardInstance(
            instance_id="enemy_1", card_id="ghoul",
            owner_id="scenario", controller_id="scenario",
        )
        ctx = EventContext(
            game_state=state, event=GameEvent.ENEMY_ATTACKS,
            investigator_id="inv1", enemy_id="enemy_1",
        )
        bus.emit(ctx)
        assert ctx.cancelled is True
        assert ci.uses["charges"] == 2
        assert ctx.extra["suggestion_attack_cancelled"] == "enemy_1"

    def test_reaction_ignores_elite(self, setup):
        state, bus, inv, impl, ci = setup
        state.cards_in_play["boss_1"] = CardInstance(
            instance_id="boss_1", card_id="boss",
            owner_id="scenario", controller_id="scenario",
        )
        ctx = EventContext(
            game_state=state, event=GameEvent.ENEMY_ATTACKS,
            investigator_id="inv1", enemy_id="boss_1",
        )
        bus.emit(ctx)
        assert ctx.cancelled is False
        assert ci.uses["charges"] == 3

    def test_reaction_cancels_attack_of_opportunity(self, setup):
        state, bus, inv, impl, ci = setup
        state.cards_in_play["enemy_1"] = CardInstance(
            instance_id="enemy_1", card_id="ghoul",
            owner_id="scenario", controller_id="scenario",
        )
        ctx = EventContext(
            game_state=state, event=GameEvent.ATTACK_OF_OPPORTUNITY,
            investigator_id="inv1", enemy_id="enemy_1",
        )
        bus.emit(ctx)
        assert ctx.cancelled is True
        assert ci.uses["charges"] == 2

    def test_no_cancel_without_charges(self, setup):
        state, bus, inv, impl, ci = setup
        ci.uses["charges"] = 0
        state.cards_in_play["enemy_1"] = CardInstance(
            instance_id="enemy_1", card_id="ghoul",
            owner_id="scenario", controller_id="scenario",
        )
        ctx = EventContext(
            game_state=state, event=GameEvent.ENEMY_ATTACKS,
            investigator_id="inv1", enemy_id="enemy_1",
        )
        bus.emit(ctx)
        assert ctx.cancelled is False
