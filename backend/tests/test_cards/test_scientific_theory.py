"""Tests for Scientific Theory (Level 1).

官方：快速。场上限1张Composure。非直接恐惧必须先分配给科学理论。
[快速]花1资源：本次检定+1智力 / +1战斗。
"""

import pytest

from backend.cards.seeker.scientific_theory_lv1 import ScientificTheory
from backend.engine.damage import DamageEngine
from backend.engine.event_bus import EventBus
from backend.engine.skill_test import SkillTestEngine
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)
    bag.tokens = [ChaosTokenType.ZERO]

    inv_data = make_investigator_data(intellect=3, combat=3)
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        resources=3,
    )
    state.investigators["inv1"] = inv

    state.card_database["scientific_theory_lv1"] = make_asset_data(
        id="scientific_theory_lv1", name="Scientific Theory", cost=1,
        traits=["talent", "composure"], sanity=1,
    )
    inst = CardInstance(
        instance_id="inst_st", card_id="scientific_theory_lv1",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_st"] = inst
    inv.play_area.append("inst_st")

    impl = ScientificTheory("inst_st")
    impl.register(bus, "inst_st")

    damage = DamageEngine(state, bus)
    skill_test = SkillTestEngine(state, bus, bag)
    return state, bus, bag, inv, inst, impl, damage, skill_test


class TestHorrorSoak:
    def test_non_direct_horror_assigned_to_theory_first(self, setup):
        """1点非直接恐惧全部分配给科学理论（理智1），调查员不受。"""
        state, bus, bag, inv, inst, impl, damage, _ = setup
        damage.deal_damage("inv1", horror=1)
        assert inst.horror == 1
        assert inv.horror == 0
        # 理智1吸1点恐惧后被击败弃置
        assert "inst_st" not in inv.play_area
        assert "scientific_theory_lv1" in inv.discard

    def test_overflow_horror_hits_investigator(self, setup):
        """超出科学理论承受力的恐惧分配给调查员。"""
        state, bus, bag, inv, inst, impl, damage, _ = setup
        damage.deal_damage("inv1", horror=2)
        assert inv.horror == 1  # 2 - 1(分配给科学理论)
        assert "inst_st" not in inv.play_area

    def test_no_soak_after_leaving_play(self, setup):
        state, bus, bag, inv, inst, impl, damage, _ = setup
        inv.play_area.remove("inst_st")
        damage.deal_damage("inv1", horror=1)
        assert inv.horror == 1
        assert inst.horror == 0


class TestResourceBoost:
    def test_spend_boosts_intellect_test(self, setup):
        """花1资源：本次智力检定+1（3+1=4 过难度4）。"""
        state, bus, bag, inv, inst, impl, _, skill_test = setup
        assert impl.spend(state, "inv1", Skill.INTELLECT) is True
        assert inv.resources == 2
        result = skill_test.run_test(
            investigator_id="inv1", skill_type=Skill.INTELLECT,
            difficulty=4)
        assert result.success is True
        sources = result.extra.get("skill_bonus_sources", [])
        assert any(s["reason"] == "scientific_theory_lv1_boost"
                   and s["delta"] == 1 for s in sources)

    def test_spend_boosts_combat_test(self, setup):
        state, bus, bag, inv, inst, impl, _, skill_test = setup
        assert impl.spend(state, "inv1", Skill.COMBAT) is True
        result = skill_test.run_test(
            investigator_id="inv1", skill_type=Skill.COMBAT,
            difficulty=4)
        assert result.success is True

    def test_spend_requires_resources(self, setup):
        state, bus, bag, inv, inst, impl, _, skill_test = setup
        inv.resources = 0
        assert impl.spend(state, "inv1", Skill.INTELLECT) is False

    def test_willpower_not_boostable(self, setup):
        state, bus, bag, inv, inst, impl, _, skill_test = setup
        assert impl.spend(state, "inv1", Skill.WILLPOWER) is False
