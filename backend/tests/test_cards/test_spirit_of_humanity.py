"""Tests for Spirit of Humanity (Level 2)."""

import pytest
from backend.cards.survivor.spirit_of_humanity_lv2 import SpiritOfHumanity
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv

    inst = CardInstance(
        instance_id="soh_inst", card_id="spirit_of_humanity_lv2",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["soh_inst"] = inst
    inv.play_area.append("soh_inst")

    impl = SpiritOfHumanity("soh_inst")
    impl.bind_chaos_bag(bag)
    return state, bag, inv, inst, impl


class TestSpiritOfHumanity:
    def test_bless_adds_tokens_and_costs_damage_horror(self, setup):
        """祝福能力：消耗、受1伤害1恐惧、袋中+2祝福。"""
        state, bag, inv, inst, impl = setup
        before = bag.tokens.count(ChaosTokenType.BLESS)
        ok = impl.activate_bless(state, "inv1")
        assert ok
        assert inst.exhausted
        assert inv.damage == 1
        assert inv.horror == 1
        assert bag.tokens.count(ChaosTokenType.BLESS) == before + 2

    def test_curse_adds_tokens_and_heals(self, setup):
        """诅咒能力：消耗、袋中+2诅咒、治愈1伤害1恐惧。"""
        state, bag, inv, inst, impl = setup
        inv.damage = 2
        inv.horror = 2
        before = bag.tokens.count(ChaosTokenType.CURSE)
        ok = impl.activate_curse(state, "inv1")
        assert ok
        assert inst.exhausted
        assert inv.damage == 1
        assert inv.horror == 1
        assert bag.tokens.count(ChaosTokenType.CURSE) == before + 2

    def test_requires_ready(self, setup):
        """已消耗时无法启动。"""
        state, bag, inv, inst, impl = setup
        inst.exhausted = True
        assert impl.activate_bless(state, "inv1") is False
        assert impl.activate_curse(state, "inv1") is False

    def test_heal_clamps_at_zero(self, setup):
        """无伤害/恐惧时治愈归零而不变负。"""
        state, bag, inv, inst, impl = setup
        assert impl.activate_curse(state, "inv1") is True
        assert inv.damage == 0
        assert inv.horror == 0
