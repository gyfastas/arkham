"""Tests for Medical Texts (Level 2)."""

import pytest
from backend.cards.seeker.medical_texts_lv2 import MedicalTextsLv2
from backend.engine.event_bus import EventBus
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data(intellect=4)
    state.card_database[inv_data.id] = inv_data
    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data,
        location_id="test_location", damage=3,
    )
    state.investigators["inv1"] = inv
    state.locations["test_location"] = LocationState(
        location_id="test_location", card_data=loc_data,
    )

    inst = CardInstance(
        instance_id="mt_1", card_id="medical_texts_lv2",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["mt_1"] = inst
    inv.play_area.append("mt_1")

    impl = MedicalTextsLv2("mt_1")
    impl.register(bus, "mt_1")
    impl.bind_chaos_bag(bag)
    return state, bus, bag, inv, inst, impl


class TestMedicalTextsLv2:
    def test_success_by_two_heals_two(self, setup):
        """智力4 对难度2（0标记）：超2点 → 治愈2点伤害。"""
        state, bus, bag, inv, inst, impl = setup
        bag.tokens = [ChaosTokenType.ZERO]
        assert impl.activate(state, "inv1") is True
        assert inv.damage == 1  # 3 - 2

    def test_plain_success_heals_one(self, setup):
        """成功但超出不足2点：治愈1点。"""
        state, bus, bag, inv, inst, impl = setup
        bag.tokens = [ChaosTokenType.MINUS_2]  # 4-2=2 对2，超0点
        impl.activate(state, "inv1")
        assert inv.damage == 2  # 3 - 1

    def test_failure_exhausts_instead_of_damage(self, setup):
        """失败：本卡未消耗 → 自动选择消耗（不受伤害）。"""
        state, bus, bag, inv, inst, impl = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL]
        impl.activate(state, "inv1")
        assert inst.exhausted is True
        assert inv.damage == 3  # 不变

    def test_failure_while_exhausted_deals_damage(self, setup):
        """失败且本卡已消耗：对该调查员造成1点伤害。"""
        state, bus, bag, inv, inst, impl = setup
        inst.exhausted = True
        bag.tokens = [ChaosTokenType.AUTO_FAIL]
        impl.activate(state, "inv1")
        assert inv.damage == 4  # 3 + 1
