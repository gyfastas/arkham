"""Tests for Sweeping Kick (Level 1). (08023)

攻击：敏捷加入技能值，+1伤害；成功则自动躲避被攻击的敌人。
"""

import pytest

from backend.cards.guardian.sweeping_kick_lv1 import SweepingKick
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, PlayerClass
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(combat=3, agility=4)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="sweeping_kick_lv1", name="Sweeping Kick", cost=1,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(make_enemy_data(id="ghoul", fight=4, health=5))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(SweepingKick)

    enemy = CardInstance(
        instance_id="enemy_1", card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    g.state.cards_in_play["enemy_1"] = enemy
    g.state.get_investigator("inv1").threat_area.append("enemy_1")

    g.chaos_bag.tokens = [ChaosTokenType.ZERO]

    inv = g.state.get_investigator("inv1")
    inv.hand.append("sweeping_kick_lv1")
    inv.actions_remaining = 3
    return g


class TestSweepingKick:
    def test_agility_added_and_auto_evade(self, game):
        """战斗3+敏捷4=7 vs 战斗4 成功；+1伤害；敌人被自动躲避。"""
        inv = game.state.get_investigator("inv1")

        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="sweeping_kick_lv1",
        )
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
        )

        enemy = game.state.get_card_instance("enemy_1")
        assert enemy is not None
        assert enemy.damage == 2  # 1基础 + 1扫堂腿
        # 自动躲避：横置、脱离交战、放回地点
        assert enemy.exhausted is True
        assert "enemy_1" not in inv.threat_area
        assert "enemy_1" in game.state.locations["test_location"].enemies

    def test_no_evade_on_failure(self, game):
        """攻击失败（袋中 auto_fail）：不躲避敌人。"""
        game.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]
        inv = game.state.get_investigator("inv1")

        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="sweeping_kick_lv1",
        )
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
        )

        enemy = game.state.get_card_instance("enemy_1")
        assert enemy.damage == 0
        assert enemy.exhausted is False
        assert "enemy_1" in inv.threat_area
