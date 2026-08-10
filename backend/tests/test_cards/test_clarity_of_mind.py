"""Tests for Clarity of Mind (Level 0). (02030)

使用(3充能)。【行动】花1充能：治愈你所在地点一位调查员1点恐惧。
（官方卡面无横置要求。）
"""

import pytest
from backend.cards.mystic.clarity_of_mind_lv0 import ClarityOfMind
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        horror=2,
    )
    state.investigators["inv1"] = inv

    state.card_database["clarity_of_mind_lv0"] = make_asset_data(
        id="clarity_of_mind_lv0", name="Clarity of Mind", traits=["spell"],
        uses={"charges": 3},
    )
    inst = CardInstance(
        instance_id="inst_com", card_id="clarity_of_mind_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"charges": 3}
    state.cards_in_play["inst_com"] = inst
    inv.play_area.append("inst_com")

    impl = ClarityOfMind("inst_com")
    return state, inv, inst, impl


class TestClarityOfMind:
    def test_heal_self_spends_charge_no_exhaust(self, setup):
        state, inv, inst, impl = setup
        assert impl.activate(state, "inv1") is True
        assert inv.horror == 1
        assert inst.uses["charges"] == 2
        assert inst.exhausted is False

    def test_heal_other_investigator_at_same_location(self, setup):
        state, inv, inst, impl = setup
        other_data = make_investigator_data(id="other_inv", name="Other")
        state.card_database[other_data.id] = other_data
        other = InvestigatorState(
            investigator_id="inv2", card_data=other_data, location_id="loc1",
            horror=1,
        )
        state.investigators["inv2"] = other
        assert impl.activate(state, "inv1", target_investigator_id="inv2") is True
        assert other.horror == 0
        assert inv.horror == 2

    def test_cannot_heal_other_location(self, setup):
        state, inv, inst, impl = setup
        other_data = make_investigator_data(id="other_inv", name="Other")
        state.card_database[other_data.id] = other_data
        other = InvestigatorState(
            investigator_id="inv2", card_data=other_data, location_id="loc2",
            horror=1,
        )
        state.investigators["inv2"] = other
        assert impl.activate(state, "inv1", target_investigator_id="inv2") is False

    def test_no_charges_no_heal(self, setup):
        state, inv, inst, impl = setup
        inst.uses["charges"] = 0
        assert impl.activate(state, "inv1") is False
        assert inv.horror == 2
