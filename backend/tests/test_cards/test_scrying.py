"""Tests for Scrying (Level 0). (01061)

【行动】横置+1充能：查看任一调查员牌库或遭遇牌堆顶3张，以任意顺序放回顶。
（无置底；重排经 order 参数，默认保持原顺序。）
"""

import pytest
from backend.cards.mystic.scrying_lv0 import Scrying
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
        deck=["c1", "c2", "c3", "c4", "c5"],
    )
    state.investigators["inv1"] = inv

    state.card_database["scrying_lv0"] = make_asset_data(
        id="scrying_lv0", name="Scrying", traits=["spell"],
        uses={"charges": 3},
    )
    inst = CardInstance(
        instance_id="inst_scrying", card_id="scrying_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"charges": 3}
    state.cards_in_play["inst_scrying"] = inst
    inv.play_area.append("inst_scrying")

    impl = Scrying("inst_scrying")
    return state, inv, inst, impl


class TestScrying:
    def test_activate_spends_charge_and_exhausts(self, setup):
        state, inv, inst, impl = setup
        assert impl.activate(state, "inv1") is True
        assert inst.uses["charges"] == 2
        assert inst.exhausted is True

    def test_default_keeps_order_no_bottom(self, setup):
        """默认保持原顺序放回顶；牌库底不变（官方无置底）。"""
        state, inv, inst, impl = setup
        assert impl.activate(state, "inv1") is True
        assert inv.deck == ["c1", "c2", "c3", "c4", "c5"]

    def test_order_param_reorders_top3(self, setup):
        """order 参数可重排顶3张（其余不动）。"""
        state, inv, inst, impl = setup
        assert impl.activate(state, "inv1", order=[2, 0, 1]) is True
        assert inv.deck == ["c3", "c1", "c2", "c4", "c5"]

    def test_can_target_other_investigator(self, setup):
        state, inv, inst, impl = setup
        other_data = make_investigator_data(id="other_inv", name="Other")
        state.card_database[other_data.id] = other_data
        other = InvestigatorState(
            investigator_id="inv2", card_data=other_data, location_id="loc1",
            deck=["x1", "x2", "x3", "x4"],
        )
        state.investigators["inv2"] = other
        assert impl.activate(state, "inv1", target_investigator_id="inv2",
                             order=[1, 0, 2]) is True
        assert other.deck == ["x2", "x1", "x3", "x4"]
        assert inv.deck == ["c1", "c2", "c3", "c4", "c5"]

    def test_can_target_encounter_deck(self, setup):
        """可选遭遇牌堆为目标。"""
        state, inv, inst, impl = setup
        state.scenario.encounter_deck = ["e1", "e2", "e3", "e4"]
        assert impl.activate(state, "inv1", target_encounter_deck=True,
                             order=[2, 1, 0]) is True
        assert state.scenario.encounter_deck == ["e3", "e2", "e1", "e4"]
        assert inv.deck == ["c1", "c2", "c3", "c4", "c5"]

    def test_cannot_activate_exhausted_or_empty(self, setup):
        state, inv, inst, impl = setup
        inst.exhausted = True
        assert impl.activate(state, "inv1") is False
        inst.exhausted = False
        inst.uses["charges"] = 0
        assert impl.activate(state, "inv1") is False
