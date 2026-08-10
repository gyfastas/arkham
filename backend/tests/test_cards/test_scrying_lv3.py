"""Tests for Scrying (Level 3). (03236)

【快速】横置+1充能：查看任一调查员牌库或遭遇牌堆顶3张，任意顺序放回顶；
查看的牌中有 Terror 或 Omen 卡时受到1恐惧。（无抽牌。）
"""

import pytest
from backend.cards.mystic.scrying_lv3 import ScryingLv3
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import (
    make_asset_data, make_event_data, make_investigator_data,
)


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        deck=["c1", "c2", "c3", "c4"],
    )
    state.investigators["inv1"] = inv

    state.card_database["scrying_lv3"] = make_asset_data(
        id="scrying_lv3", name="Scrying", traits=["spell"],
        uses={"charges": 3},
    )
    terror = make_event_data(id="terror_card", name="Terror Card")
    terror.traits = ["terror"]
    state.card_database["terror_card"] = terror

    inst = CardInstance(
        instance_id="inst_scrying3", card_id="scrying_lv3",
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"charges": 3}
    state.cards_in_play["inst_scrying3"] = inst
    inv.play_area.append("inst_scrying3")

    impl = ScryingLv3("inst_scrying3")
    return state, inv, inst, impl


class TestScryingLv3:
    def test_no_draw_after_looking(self, setup):
        """旧实现的"查看后抽1张"为编造，已删除。"""
        state, inv, inst, impl = setup
        hand_before = list(inv.hand)
        assert impl.activate(state, "inv1") is True
        assert inv.hand == hand_before
        assert len(inv.deck) == 4

    def test_horror_when_terror_among_top3(self, setup):
        """顶3中有 Terror 卡：受1恐惧。"""
        state, inv, inst, impl = setup
        inv.deck = ["c1", "terror_card", "c3", "c4"]
        assert impl.activate(state, "inv1") is True
        assert inv.horror == 1

    def test_no_horror_when_terror_beyond_top3(self, setup):
        state, inv, inst, impl = setup
        inv.deck = ["c1", "c2", "c3", "terror_card"]
        assert impl.activate(state, "inv1") is True
        assert inv.horror == 0

    def test_horror_when_omen_in_encounter_deck(self, setup):
        state, inv, inst, impl = setup
        omen = make_event_data(id="omen_card", name="Omen Card")
        omen.traits = ["omen"]
        state.card_database["omen_card"] = omen
        state.scenario.encounter_deck = ["omen_card", "e2", "e3"]
        assert impl.activate(state, "inv1", target_encounter_deck=True) is True
        assert inv.horror == 1
