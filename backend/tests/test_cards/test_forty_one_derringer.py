"""Tests for .41 Derringer (Level 0)."""

import pytest
from backend.cards.rogue.forty_one_derringer_lv0 import FortyOneDerringer
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

    impl = FortyOneDerringer("derringer_inst")
    impl.register(bus, "derringer_inst")

    ci = CardInstance(
        instance_id="derringer_inst", card_id="forty_one_derringer_lv0",
        owner_id="inv1", controller_id="inv1",
        uses={"ammo": 3},
    )
    state.cards_in_play["derringer_inst"] = ci
    inv.play_area.append("derringer_inst")
    return state, bus, inv, impl, ci


def _skill_value_ctx(state, source="derringer_inst"):
    return EventContext(
        game_state=state,
        event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id="inv1",
        skill_type=Skill.COMBAT,
        amount=3,
        source=source,
    )


def _success_ctx(state, modified_skill, difficulty, source="derringer_inst"):
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


class TestFortyOneDerringer:
    def test_card_id(self, setup):
        """.41 Derringer has correct card_id."""
        assert FortyOneDerringer.card_id == "forty_one_derringer_lv0"

    def test_combat_bonus(self, setup):
        """+2 combat when fighting with this weapon."""
        state, bus, inv, impl, ci = setup
        ctx = _skill_value_ctx(state)
        bus.emit(ctx)
        assert ctx.amount == 5

    def test_no_combat_bonus_for_other_weapon(self, setup):
        state, bus, inv, impl, ci = setup
        ctx = _skill_value_ctx(state, source="other_weapon")
        bus.emit(ctx)
        assert ctx.amount == 3

    def test_margin_damage_at_2_or_more(self, setup):
        """Succeed by 2 or more: +1 damage via bonus_damage channel."""
        state, bus, inv, impl, ci = setup
        ctx = _success_ctx(state, modified_skill=5, difficulty=3)
        bus.emit(ctx)
        assert ctx.extra["bonus_damage"] == 1

    def test_no_margin_damage_below_2(self, setup):
        """Succeed by exactly 1: no bonus damage (official text is 2 or more)."""
        state, bus, inv, impl, ci = setup
        ctx = _success_ctx(state, modified_skill=4, difficulty=3)
        bus.emit(ctx)
        assert "bonus_damage" not in ctx.extra

    def test_ammo_spent_on_hit(self, setup):
        """Ammo is spent when the attack deals damage (hit)."""
        state, bus, inv, impl, ci = setup
        ctx = EventContext(
            game_state=state,
            event=GameEvent.DAMAGE_DEALT,
            investigator_id="inv1",
            amount=1,
            source="derringer_inst",
        )
        bus.emit(ctx)
        assert ci.uses["ammo"] == 2

    def test_no_clue_on_defeat(self, setup):
        """The fabricated clue-on-defeat effect is gone."""
        state, bus, inv, impl, ci = setup
        ctx = EventContext(
            game_state=state,
            event=GameEvent.ENEMY_DEFEATED,
            investigator_id="inv1",
            enemy_id="enemy_1",
            extra={"card_id": "forty_one_derringer_lv0"},
        )
        bus.emit(ctx)
        assert inv.clues == 0
