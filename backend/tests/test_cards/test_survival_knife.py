"""Tests for Survival Knife (Level 0). (04017)

[action]攻击+1战斗；敌军阶段被敌人攻击受伤后消耗本卡反击（+2战斗/+1伤害）。
"""

import pytest

from backend.cards.guardian.survival_knife_lv0 import SurvivalKnife
from backend.engine.game import Game
from backend.models.enums import (
    Action, CardType, ChaosTokenType, Phase, PlayerClass, SlotType,
)
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]
    inv_data = make_investigator_data(combat=4)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(CardData(
        id="survival_knife_lv0", name="Survival Knife", name_cn="求生匕首",
        type=CardType.ASSET, card_class=PlayerClass.GUARDIAN, cost=2,
        slots=[SlotType.HAND], traits=["item", "weapon", "melee"],
    ))
    g.register_card_data(make_enemy_data(id="ghoul", fight=3, health=5))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(SurvivalKnife)

    knife = CardInstance(
        instance_id="knife_1", card_id="survival_knife_lv0",
        owner_id="inv1", controller_id="inv1", slot_used=[SlotType.HAND],
    )
    g.state.cards_in_play["knife_1"] = knife
    inv = g.state.get_investigator("inv1")
    inv.play_area.append("knife_1")
    inv.actions_remaining = 3
    g.card_registry.activate_card(
        "survival_knife_lv0", "knife_1", g.event_bus, chaos_bag=g.chaos_bag)

    enemy = CardInstance(
        instance_id="enemy_1", card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    g.state.cards_in_play["enemy_1"] = enemy
    inv.threat_area.append("enemy_1")
    return g


class TestSurvivalKnife:
    def test_normal_attack_plus_1(self, game):
        """普通攻击（combat 4+1=5 vs 4 fight）：用 fight4 敌人验证+1生效。"""
        game.register_card_data(make_enemy_data(id="ghoul", fight=4, health=5))
        impl = game.card_registry.active_instances["knife_1"]
        assert impl.activate(game.state, "inv1") is True
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
            weapon_instance_id="knife_1",
        )
        # 4+1=5 ≥ 4 成功，无加伤：1点
        assert game.state.get_card_instance("enemy_1").damage == 1

    def test_retaliation_after_enemy_phase_damage(self, game):
        """敌军阶段受敌人攻击伤害后：匕首横置，反击+2战斗/+1伤害。"""
        game.state.scenario.current_phase = Phase.ENEMY
        knife = game.state.get_card_instance("knife_1")
        inv = game.state.get_investigator("inv1")

        game.damage_engine.deal_damage("inv1", damage=1, source="enemy_1")
        assert inv.damage == 1
        assert knife.exhausted is True

        # 会话层随后以本卡发起反击（目标为攻击者）
        impl = game.card_registry.active_instances["knife_1"]
        assert impl.retaliate_target == "enemy_1"
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
            weapon_instance_id="knife_1",
        )
        # 4+2=6 vs 3 成功；伤害=1基础+1反击=2
        assert game.state.get_card_instance("enemy_1").damage == 2

    def test_no_retaliation_outside_enemy_phase(self, game):
        """非敌军阶段受伤（如反击关键词）：不武装反击、不横置。"""
        game.state.scenario.current_phase = Phase.INVESTIGATION
        knife = game.state.get_card_instance("knife_1")

        game.damage_engine.deal_damage("inv1", damage=1, source="enemy_1")
        assert knife.exhausted is False
