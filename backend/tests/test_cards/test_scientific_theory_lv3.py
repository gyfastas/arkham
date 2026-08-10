"""Tests for Scientific Theory (Level 3).

官方：快速。场上限1张[[沉稳]]。你获得+1[intellect]和+1[combat]。
非直接伤害/恐惧必须先分配给科学理论（生命1/理智3）。
[快速]花1资源：本次检定+1[intellect]或+1[combat]。
"""

import pytest

from backend.cards.seeker.scientific_theory_lv3 import ScientificTheoryLv3
from backend.engine.damage import DamageEngine
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_scientific_theory_lv3")
    g.chaos_bag.seed(42)
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]

    inv_data = make_investigator_data(intellect=3, combat=3)
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a")
    g.register_card_data(loc_data)
    g.add_investigator("player", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_data, clues=0)

    g.register_card_data(make_asset_data(
        id="scientific_theory_lv3", name="Scientific Theory", cost=0,
        traits=["talent", "composure"], health=1, sanity=3))
    inst = CardInstance(
        instance_id="inst_st3", card_id="scientific_theory_lv3",
        owner_id="player", controller_id="player",
    )
    g.state.cards_in_play["inst_st3"] = inst
    g.state.get_investigator("player").play_area.append("inst_st3")

    impl = ScientificTheoryLv3("inst_st3")
    impl.register(g.event_bus, "inst_st3")
    return g, impl


class TestConstantBonus:
    def test_intellect_and_combat_plus_one(self, game):
        """恒定+1：智力检定3+1=4过难度4。"""
        g, _impl = game
        result = g.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.INTELLECT,
            difficulty=4,
        )
        assert result.success is True
        sources = result.extra.get("skill_bonus_sources", [])
        assert any(s["reason"] == "scientific_theory_lv3_constant"
                   and s["delta"] == 1 for s in sources)

    def test_no_bonus_for_other_skills(self, game):
        g, _impl = game
        result = g.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.AGILITY,
            difficulty=4,
        )
        assert result.success is False  # 3 < 4


class TestSoak:
    def test_damage_assigned_to_theory_first(self, game):
        """非直接伤害1点全部分配给科学理论（生命1）→ 被击败弃置。"""
        g, _impl = game
        inv = g.state.get_investigator("player")
        inst = g.state.get_card_instance("inst_st3")
        g.damage_engine.deal_damage("player", damage=1)
        assert inst.damage == 1
        assert inv.damage == 0
        # 生命耗尽：被击败
        assert "inst_st3" not in inv.play_area
        assert "scientific_theory_lv3" in inv.discard

    def test_horror_soaked_up_to_sanity(self, game):
        """非直接恐惧4点：3点分配给科学理论（理智3），溢出1点给调查员。"""
        g, _impl = game
        inv = g.state.get_investigator("player")
        inst = g.state.get_card_instance("inst_st3")
        g.damage_engine.deal_damage("player", horror=4)
        assert inst.horror == 3
        assert inv.horror == 1
        assert "inst_st3" not in inv.play_area  # 理智耗尽被击败


class TestResourcePump:
    def test_spend_boosts_combat(self, game):
        """花1资源：本次战斗检定再+1（3+1恒定+1泵=5过难度5）。"""
        g, impl = game
        inv = g.state.get_investigator("player")
        inv.resources = 2
        assert impl.spend(g.state, "player", Skill.COMBAT) is True
        result = g.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.COMBAT,
            difficulty=5,
        )
        assert result.success is True
