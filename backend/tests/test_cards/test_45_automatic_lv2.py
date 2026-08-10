"""Tests for .45 Automatic (Level 2). (03190)

[行动]花费1子弹：攻击。本次攻击+2战斗、+1伤害，忽略反击关键词。
"""

import pytest
from backend.cards.guardian.forty_five_automatic_lv2 import FortyFiveAutomaticLv2
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

    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(CardData(
        id="45_automatic_lv2", name=".45 Automatic", name_cn=".45自动手枪",
        type=CardType.ASSET, card_class=PlayerClass.GUARDIAN, cost=4,
        slots=[SlotType.HAND], traits=["item", "weapon", "firearm"],
        uses={"ammo": 4}, skill_icons={"combat": 1, "agility": 1},
    ))
    g.register_card_data(make_enemy_data(fight=3, health=5))
    g.register_card_data(make_enemy_data(
        id="retaliate_enemy", name="Retaliator", fight=20, health=9,
        keywords=["retaliate"],
    ))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=2)
    g.card_registry.register_class(FortyFiveAutomaticLv2)
    return g


def _equip(game, ammo=4):
    inv = game.state.get_investigator("inv1")
    inst = CardInstance(
        instance_id="gun_1", card_id="45_automatic_lv2",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND], uses={"ammo": ammo},
    )
    game.state.cards_in_play["gun_1"] = inst
    inv.play_area.append("gun_1")
    game.card_registry.activate_card("45_automatic_lv2", "gun_1", game.event_bus)
    return inst


def _spawn(game, card_id="test_enemy", instance_id="enemy_1"):
    enemy = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    game.state.get_investigator("inv1").threat_area.append(instance_id)
    return enemy


class TestFortyFiveAutomaticLv2:
    def test_combat_and_damage_bonus(self, game):
        """+2战斗 +1伤害：战斗3+2=5 对战斗值3，命中造成2点伤害。"""
        gun = _equip(game)
        enemy = _spawn(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id="gun_1",
        )
        assert gun.uses["ammo"] == 3
        assert enemy.damage == 2
        result = game.skill_test_engine._last_result
        assert result.modified_skill == 5  # 3 + 2枪 + 0标记

    def test_ignores_retaliate(self, game):
        """攻击反击敌人失败时不受反击伤害；反击关键词在检定后还原。"""
        _equip(game)
        _spawn(game, card_id="retaliate_enemy")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]  # 5 vs 20 必败

        inv = game.state.get_investigator("inv1")
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id="gun_1",
        )
        assert inv.damage == 0 and inv.horror == 0  # 反击被忽略
        enemy_data = game.state.get_card_data("retaliate_enemy")
        assert "retaliate" in enemy_data.keywords  # 检定结束后还原

    def test_retaliate_still_works_without_weapon(self, game):
        """对照：徒手攻击同一反击敌人失败会正常受反击。"""
        _spawn(game, card_id="retaliate_enemy")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]  # 3 vs 20 必败

        inv = game.state.get_investigator("inv1")
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
        )
        assert inv.damage == 1 and inv.horror == 1

    def test_no_ammo_cancels_attack(self, game):
        """无子弹时不能以本武器攻击。"""
        _equip(game, ammo=0)
        enemy = _spawn(game)
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        ok = game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id="gun_1",
        )
        assert ok is False
        assert inv.actions_remaining == 3
        assert enemy.damage == 0
