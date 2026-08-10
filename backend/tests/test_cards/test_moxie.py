"""Tests for Moxie (Level 1)."""

import pytest
from backend.cards.rogue.moxie_lv1 import Moxie
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

    inv_data = make_investigator_data(willpower=3, agility=3)
    state.card_database[inv_data.id] = inv_data
    state.card_database["moxie_lv1"] = make_asset_data(
        id="moxie_lv1", cost=1, sanity=1,
        traits=["talent", "composure"],
    )

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        resources=3,
    )
    state.investigators["inv1"] = inv

    ci = CardInstance(
        instance_id="moxie_inst", card_id="moxie_lv1",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["moxie_inst"] = ci
    inv.play_area.append("moxie_inst")

    impl = Moxie("moxie_inst")
    impl.register(bus, "moxie_inst")
    return state, bus, inv, impl, ci


def _horror_ctx(state, amount):
    return EventContext(
        game_state=state, event=GameEvent.HORROR_ASSIGNED,
        investigator_id="inv1", amount=amount, source="enemy_1",
    )


class TestMoxie:
    def test_card_id(self):
        assert Moxie.card_id == "moxie_lv1"

    def test_horror_redirected_to_moxie(self, setup):
        """Non-direct horror must be assigned to Moxie first."""
        state, bus, inv, impl, ci = setup
        ctx = _horror_ctx(state, 2)
        bus.emit(ctx)

        assert ci.horror == 1  # soaked up to its sanity
        assert ctx.amount == 1  # investigator's portion reduced
        assert ctx.extra["moxie_soaked"] == 1

    def test_moxie_defeated_when_full_of_horror(self, setup):
        """Moxie (sanity 1) is defeated after soaking 1 horror."""
        state, bus, inv, impl, ci = setup
        ctx = _horror_ctx(state, 1)
        bus.emit(ctx)

        assert "moxie_inst" not in inv.play_area
        assert "moxie_inst" not in state.cards_in_play
        assert "moxie_lv1" in inv.discard
        assert ctx.extra["moxie_defeated"] is True

    def test_partial_soak_survives_with_more_sanity(self, setup):
        """Custom sanity-2 copy soaks 1 horror and stays in play."""
        state, bus, inv, impl, ci = setup
        state.card_database["moxie_lv1"].sanity = 2
        ctx = _horror_ctx(state, 1)
        bus.emit(ctx)

        assert ci.horror == 1
        assert ctx.amount == 0
        assert "moxie_inst" in inv.play_area

    def test_no_redirect_when_not_in_play(self, setup):
        state, bus, inv, impl, ci = setup
        inv.play_area.remove("moxie_inst")
        ctx = _horror_ctx(state, 2)
        bus.emit(ctx)
        assert ctx.amount == 2
        assert ci.horror == 0

    def test_resource_pump_willpower_and_agility(self, setup):
        """Fast: spend 1 resource for +1 willpower or +1 agility this test."""
        state, bus, inv, impl, ci = setup
        assert impl.spend(state, "inv1", Skill.WILLPOWER) is True
        assert impl.spend(state, "inv1", Skill.AGILITY) is True
        assert inv.resources == 1

        ctx = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.WILLPOWER, amount=3,
        )
        bus.emit(ctx)
        assert ctx.amount == 4

        ctx2 = EventContext(
            game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="inv1", skill_type=Skill.AGILITY, amount=3,
        )
        bus.emit(ctx2)
        assert ctx2.amount == 4
