"""Tests for Mechanic's Wrench (Level 0)."""

import pytest
from backend.cards.neutral.mechanics_wrench_lv0 import MechanicsWrench
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data(combat=4))
    g.register_card_data(make_location_data())
    g.register_card_data(make_asset_data(
        id="mechanics_wrench_lv0", name="Mechanic's Wrench", cost=2,
    ))
    g.register_card_data(make_enemy_data(
        id="ghoul", name="Ghoul", fight=2, health=6, evade=2,
        damage=1, horror=1,
    ))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(MechanicsWrench)
    inv = g.state.get_investigator("inv1")
    inv.hand.append("mechanics_wrench_lv0")
    inv.resources = 5
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]

    # 敌人初始在地点上未交战（避免打出扳手时的借机攻击干扰断言）
    enemy = CardInstance(
        instance_id="enemy_1", card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    g.state.cards_in_play["enemy_1"] = enemy
    g.state.get_location("test_location").enemies.append("enemy_1")
    return g


def _play(game):
    game.action_resolver.perform_action(
        "inv1", Action.PLAY, card_id="mechanics_wrench_lv0",
    )
    game.state.get_location("test_location").enemies.remove("enemy_1")
    game.state.get_investigator("inv1").threat_area.append("enemy_1")
    return next(
        i for i in game.card_registry.active_instances.values()
        if isinstance(i, MechanicsWrench)
    )


class TestMechanicsWrench:
    def test_provoke_enemy_attacks_you(self, game):
        """[fast] 横置：选择的敌人攻击你（1伤害1恐惧）。"""
        impl = _play(game)
        inv = game.state.get_investigator("inv1")
        assert impl.activate_provoke(game.state, "inv1",
                                     enemy_instance_id="enemy_1") is True
        assert inv.damage == 1
        assert inv.horror == 1
        inst = game.state.get_card_instance(impl.instance_id)
        assert inst.exhausted is True

    def test_fight_bonus_against_attacker(self, game):
        """攻击过你的敌人：战斗+2且+1伤害（1基础+1=2）。"""
        impl = _play(game)
        impl.activate_provoke(game.state, "inv1", enemy_instance_id="enemy_1")
        enemy = game.state.get_card_instance("enemy_1")
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
            weapon_instance_id=impl.instance_id,
        )
        assert enemy.damage == 2

    def test_fight_blocked_against_non_attacker(self, game):
        """未攻击过你的敌人：战斗能力被取消（行动不消耗）。"""
        impl = _play(game)
        inv = game.state.get_investigator("inv1")
        actions_before = inv.actions_remaining
        ok = game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
            weapon_instance_id=impl.instance_id,
        )
        assert ok is False
        assert inv.actions_remaining == actions_before
        assert game.state.get_card_instance("enemy_1").damage == 0
