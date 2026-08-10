"""Tests for Brute Force (Level 1)."""

import pytest

from backend.cards.survivor.brute_force_lv1 import BruteForce
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
    make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_skill_data(
        id="brute_force_lv1", skill_icons={"combat": 1}))
    g.register_card_data(make_enemy_data(fight=3, health=10, evade=3))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(BruteForce)
    inv = g.state.get_investigator("inv1")
    g.state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    inv.threat_area.append("enemy_1")
    return g


class TestBruteForce:
    def test_card_registered(self, game):
        assert "brute_force_lv1" in game.card_registry.registered_cards

    def test_success_by_2_deals_bonus_damage(self, game):
        """投入的战斗检定成功且超出≥2：+2伤害（共3点）。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["brute_force_lv1"]
        # 3基础+1印刷+2加值+1标记 = 7 vs 3，超出4
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]
        assert game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
            committed_cards=["brute_force_lv1"]) is True
        enemy = game.state.get_card_instance("enemy_1")
        assert enemy.damage == 3  # 1基础 + 2卡面

    def test_success_by_less_than_2_no_bonus(self, game):
        """成功但超出不足2：仅基础伤害。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["brute_force_lv1"]
        # 3+1+2-2 = 4 vs 3，超出1
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_2]
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
            committed_cards=["brute_force_lv1"])
        enemy = game.state.get_card_instance("enemy_1")
        assert enemy.damage == 1

    def test_extra_icons_on_combat_test(self, game):
        """投入战斗检定：额外+2图标。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["brute_force_lv1"]
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test(
            "inv1", Skill.COMBAT, 3, committed_card_ids=["brute_force_lv1"])
        assert result.committed_icons == 3  # 1印刷 + 2加值
