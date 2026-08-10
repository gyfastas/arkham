"""Tests for The Home Front (Level 0) — Mark Harrigan signature skill."""

from backend.cards.neutral.the_home_front_lv0 import TheHomeFront
from backend.models.enums import Action, ChaosTokenType
from backend.models.state import CardInstance
from backend.tests.conftest import make_enemy_data, make_skill_data


def _setup(game):
    game.register_card_data(make_skill_data(
        id="the_home_front_lv0", skill_icons={"combat": 4}))
    game.register_card_data(make_enemy_data(id="ghoul", fight=3, health=5))
    game.card_registry.register_class(TheHomeFront)

    inv = game.state.get_investigator("test_investigator")
    inv.hand.append("the_home_front_lv0")
    enemy = CardInstance(
        instance_id="e1", card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play["e1"] = enemy
    inv.threat_area.append("e1")
    return inv, enemy


class TestTheHomeFront:
    def test_successful_attack_moves_damage(self, game):
        """攻击成功：马克1点伤害移动到敌人（敌人共受2点伤害）。"""
        inv, enemy = _setup(game)
        inv.damage = 2
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]  # 3+4=7 vs 3 成功

        game.action_resolver.perform_action(
            "test_investigator", Action.FIGHT,
            enemy_instance_id="e1", committed_cards=["the_home_front_lv0"],
        )
        assert enemy.damage == 2  # 1基础 + 1移动
        assert inv.damage == 1

    def test_no_damage_on_mark_no_bonus(self, game):
        """马克无伤害：不移动，敌人只受1点基础伤害。"""
        inv, enemy = _setup(game)
        inv.damage = 0
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        game.action_resolver.perform_action(
            "test_investigator", Action.FIGHT,
            enemy_instance_id="e1", committed_cards=["the_home_front_lv0"],
        )
        assert enemy.damage == 1
        assert inv.damage == 0

    def test_failed_attack_no_move(self, game):
        inv, enemy = _setup(game)
        inv.damage = 2
        game.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]

        game.action_resolver.perform_action(
            "test_investigator", Action.FIGHT,
            enemy_instance_id="e1", committed_cards=["the_home_front_lv0"],
        )
        assert enemy.damage == 0
        assert inv.damage == 2
