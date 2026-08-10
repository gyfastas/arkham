"""Tests for Liquid Courage (Level 0)."""

import pytest
from backend.cards.rogue.liquid_courage_lv0 import LiquidCourage
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
    )
    state.investigators["inv1"] = inv

    ci = CardInstance(
        instance_id="lc_inst", card_id="liquid_courage_lv0",
        owner_id="inv1", controller_id="inv1",
        uses={"supplies": 4},
    )
    state.cards_in_play["lc_inst"] = ci
    inv.play_area.append("lc_inst")

    impl = LiquidCourage("lc_inst")
    return state, inv, impl, ci


class TestLiquidCourage:
    def test_card_id(self):
        assert LiquidCourage.card_id == "liquid_courage_lv0"

    def test_activate_heals_1_horror(self, setup):
        state, inv, impl, ci = setup
        inv.horror = 2
        assert impl.activate(state, "inv1") is True
        assert inv.horror == 1
        assert ci.uses["supplies"] == 3

    def test_activate_allowed_at_full_sanity(self, setup):
        """Target with no horror can still be chosen (the willpower test still happens)."""
        state, inv, impl, ci = setup
        inv.horror = 0
        assert impl.activate(state, "inv1") is True
        assert inv.horror == 0
        assert ci.uses["supplies"] == 3

    def test_activate_fails_without_supplies(self, setup):
        state, inv, impl, ci = setup
        ci.uses["supplies"] = 0
        inv.horror = 2
        assert impl.activate(state, "inv1") is False

    def test_resolve_test_success_heals_extra(self, setup):
        state, inv, impl, ci = setup
        inv.horror = 2
        impl.resolve_test(state, "inv1", success=True)
        assert inv.horror == 1

    def test_resolve_test_failure_discards_random_card(self, setup):
        state, inv, impl, ci = setup
        inv.hand = ["card_a", "card_b"]
        impl.resolve_test(state, "inv1", success=False)
        assert len(inv.hand) == 1
        assert len(inv.discard) == 1
