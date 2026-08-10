"""Tests for Combat Training (Level 1). (03107)

非直接恐惧必须先分配给战斗训练；[快速]花1资源：本次检定+1战斗/+1敏捷。
"""

import pytest
from backend.cards.guardian.combat_training_lv1 import CombatTraining
from backend.engine.game import Game
from backend.models.enums import (
    ChaosTokenType, CardType, PlayerClass, Skill,
)
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(combat=3, agility=3)
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(CardData(
        id="combat_training_lv1", name="Combat Training", name_cn="战斗训练",
        type=CardType.ASSET, card_class=PlayerClass.GUARDIAN, cost=1,
        traits=["talent", "composure"], sanity=1, fast=True,
        skill_icons={"combat": 1, "agility": 1},
    ))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=2)
    g.card_registry.register_class(CombatTraining)

    inv = g.state.get_investigator("inv1")
    inst = CardInstance(
        instance_id="ct_1", card_id="combat_training_lv1",
        owner_id="inv1", controller_id="inv1",
    )
    g.state.cards_in_play["ct_1"] = inst
    inv.play_area.append("ct_1")
    g.card_registry.activate_card("combat_training_lv1", "ct_1", g.event_bus)
    return g


class TestCombatTraining:
    def test_spend_boosts_combat(self, game):
        """花1资源：本次战斗检定 +1（3+1=4 对难度4 成功）。"""
        inv = game.state.get_investigator("inv1")
        inv.resources = 5
        impl = game.card_registry.active_instances["ct_1"]
        assert impl.spend(game.state, "inv1", Skill.COMBAT) is True
        assert inv.resources == 4

        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test(
            "inv1", Skill.COMBAT, difficulty=4,
        )
        assert result.modified_skill == 4
        assert result.success is True

    def test_spend_boosts_agility_and_stacks(self, game):
        """敏捷同样可泵，且多次花费叠加。"""
        inv = game.state.get_investigator("inv1")
        inv.resources = 5
        impl = game.card_registry.active_instances["ct_1"]
        impl.spend(game.state, "inv1", Skill.AGILITY)
        impl.spend(game.state, "inv1", Skill.AGILITY)

        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test(
            "inv1", Skill.AGILITY, difficulty=5,
        )
        assert result.modified_skill == 5  # 3 + 2
        assert result.success is True

    def test_horror_soaked_before_investigator(self, game):
        """非直接恐惧优先由战斗训练承担（理智1：承1点后被击败离场）。"""
        inv = game.state.get_investigator("inv1")

        game.damage_engine.deal_damage("inv1", horror=1)
        assert inv.horror == 0
        # 战斗训练承1点恐惧达到理智上限，被击败
        assert "ct_1" not in inv.play_area
        assert "combat_training_lv1" in inv.discard

    def test_overflow_horror_hits_investigator(self, game):
        """超出本卡剩余理智的部分仍分给调查员。"""
        inst = game.state.get_card_instance("ct_1")
        inst.horror = 0  # 理智1，可承1点
        inv = game.state.get_investigator("inv1")

        game.damage_engine.deal_damage("inv1", horror=2)
        # 1点由战斗训练承担（被击败），另1点由调查员承担
        assert "ct_1" not in inv.play_area
        assert inv.horror == 1
