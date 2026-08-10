"""Tests for .25 Automatic (Level 0 / Level 2)."""

import importlib

import pytest
from backend.engine.game import Game
from backend.models.enums import Action, CardType, ChaosTokenType, PlayerClass, SlotType
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)

_lv0 = importlib.import_module("backend.cards.rogue.25_automatic_lv0")
_lv2 = importlib.import_module("backend.cards.rogue.25_automatic_lv2")
TwentyFiveAutomaticLv0 = _lv0.TwentyFiveAutomaticLv0
TwentyFiveAutomaticLv2 = _lv2.TwentyFiveAutomaticLv2


def _weapon_data(card_id):
    return CardData(
        id=card_id, name=".25 Automatic", name_cn=".25自动手枪",
        type=CardType.ASSET, card_class=PlayerClass.ROGUE, cost=4,
        slots=[SlotType.HAND], traits=["item", "weapon", "firearm", "illicit"],
        uses={"ammo": 4},
    )


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(combat=4, agility=4)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(_weapon_data("25_automatic_lv0"))
    g.register_card_data(_weapon_data("25_automatic_lv2"))
    enemy_data = make_enemy_data(fight=2, health=5, evade=2)
    g.register_card_data(enemy_data)

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)

    g.card_registry.register_class(TwentyFiveAutomaticLv0)
    g.card_registry.register_class(TwentyFiveAutomaticLv2)
    return g


def _equip(game, card_id):
    inv = game.state.get_investigator("inv1")
    instance_id = game.state.next_instance_id()
    inst = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND], uses={"ammo": 4},
    )
    game.state.cards_in_play[instance_id] = inst
    inv.play_area.append(instance_id)
    game.card_registry.activate_card(
        card_id, instance_id, game.event_bus, chaos_bag=game.chaos_bag)
    return instance_id


def _spawn_enemy(game, exhausted=False, engaged=True):
    enemy = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
        exhausted=exhausted,
    )
    game.state.cards_in_play["enemy_1"] = enemy
    inv = game.state.get_investigator("inv1")
    if engaged:
        inv.threat_area.append("enemy_1")
    else:
        game.state.locations["test_location"].enemies.append("enemy_1")
    return enemy


class TestTwentyFiveAutomaticLv0:
    def test_exhausted_target_bonus(self, game):
        """攻击已横置敌人：+2战斗、+1伤害。"""
        weapon_id = _equip(game, "25_automatic_lv0")
        enemy = _spawn_enemy(game, exhausted=True, engaged=False)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        ok = game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=weapon_id,
        )
        assert ok is True
        result = game.skill_test_engine._last_result
        assert result.modified_skill == 4 + 2 + 0  # 战斗4 + 奖励2 + 标记0
        assert enemy.damage == 2  # 基础1 + 奖励1
        assert game.state.get_card_instance(weapon_id).uses["ammo"] == 3

    def test_ready_target_no_bonus(self, game):
        """攻击未横置敌人：无加值，仅基础1伤害（仍花1子弹）。"""
        weapon_id = _equip(game, "25_automatic_lv0")
        enemy = _spawn_enemy(game, exhausted=False, engaged=True)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=weapon_id,
        )
        result = game.skill_test_engine._last_result
        assert result.modified_skill == 4
        assert enemy.damage == 1
        assert game.state.get_card_instance(weapon_id).uses["ammo"] == 3

    def test_no_ammo_cancels_attack(self, game):
        """无子弹：攻击取消，行动不花费。"""
        weapon_id = _equip(game, "25_automatic_lv0")
        _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        game.state.get_card_instance(weapon_id).uses["ammo"] = 0

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        ok = game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=weapon_id,
        )
        assert ok is False
        assert inv.actions_remaining == 3


class TestTwentyFiveAutomaticLv2:
    def test_free_fight_after_evade(self, game):
        """[反应]躲避你所在地点的敌人后：免费攻击该敌人（花1子弹，+2/+1）。"""
        weapon_id = _equip(game, "25_automatic_lv2")
        enemy = _spawn_enemy(game, engaged=True)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        ok = game.action_resolver.perform_action(
            "inv1", Action.EVADE, enemy_instance_id="enemy_1",
        )
        assert ok is True
        # 躲避成功：敌人横置、解除交战、放回地点
        assert enemy.exhausted is True
        assert "enemy_1" not in inv.threat_area
        assert "enemy_1" in game.state.locations["test_location"].enemies
        # 反应攻击：敏捷4 vs 躲避2（0标记）成功后，战斗4+2 vs 战斗值2 → 命中
        assert enemy.damage == 2  # 基础1 + 已横置奖励1
        # 反应攻击仍花费1子弹
        assert game.state.get_card_instance(weapon_id).uses["ammo"] == 3
        assert inv.actions_remaining == 2  # 反应不花费行动

    def test_no_reaction_without_ammo(self, game):
        """无子弹时躲避成功也不触发反应攻击。"""
        weapon_id = _equip(game, "25_automatic_lv2")
        enemy = _spawn_enemy(game, engaged=True)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        game.state.get_card_instance(weapon_id).uses["ammo"] = 0

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        game.action_resolver.perform_action(
            "inv1", Action.EVADE, enemy_instance_id="enemy_1",
        )
        assert enemy.exhausted is True
        assert enemy.damage == 0
