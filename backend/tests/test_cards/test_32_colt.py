"""Tests for .32 Colt (Level 0). (03020)

[行动]花费1子弹：攻击。本次攻击造成+1伤害。无子弹时不能以本武器攻击。
"""

import pytest
from backend.cards.guardian.thirty_two_colt_lv0 import ThirtyTwoColt
from backend.engine.game import Game
from backend.models.enums import (
    Action, ChaosTokenType, CardType, PlayerClass, SlotType,
)
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(combat=4)
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(CardData(
        id="32_colt_lv0", name=".32 Colt", name_cn=".32柯尔特",
        type=CardType.ASSET, card_class=PlayerClass.GUARDIAN, cost=3,
        slots=[SlotType.HAND], traits=["item", "weapon", "firearm"],
        uses={"ammo": 6}, skill_icons={"combat": 1},
    ))
    g.register_card_data(make_enemy_data(fight=3, health=5))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=2)
    g.card_registry.register_class(ThirtyTwoColt)
    return g


def _equip(game, ammo=6):
    inv = game.state.get_investigator("inv1")
    inst = CardInstance(
        instance_id="colt_1", card_id="32_colt_lv0",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND], uses={"ammo": ammo},
    )
    game.state.cards_in_play["colt_1"] = inst
    inv.play_area.append("colt_1")
    game.card_registry.activate_card("32_colt_lv0", "colt_1", game.event_bus)
    return inst


def _spawn_enemy(game):
    enemy = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play["enemy_1"] = enemy
    game.state.get_investigator("inv1").threat_area.append("enemy_1")
    return enemy


class TestThirtyTwoColt:
    def test_fight_spends_ammo_and_deals_plus_1_damage(self, game):
        """攻击支付1子弹（无论命中），命中造成 1+1 点伤害。"""
        colt = _equip(game)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        ok = game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id="colt_1",
        )
        assert ok is True
        assert colt.uses["ammo"] == 5  # 发起时支付
        assert enemy.damage == 2  # 基础1 + 柯尔特+1

    def test_miss_still_spends_ammo(self, game):
        """未命中也消耗子弹（官方时机）。"""
        colt = _equip(game)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_8]

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id="colt_1",
        )
        assert colt.uses["ammo"] == 5
        assert enemy.damage == 0

    def test_no_ammo_cancels_attack(self, game):
        """无子弹时不能以本武器攻击（行动不消耗）。"""
        colt = _equip(game, ammo=0)
        enemy = _spawn_enemy(game)
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        ok = game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id="colt_1",
        )
        assert ok is False
        assert inv.actions_remaining == 3  # 未消耗行动
        assert enemy.damage == 0
