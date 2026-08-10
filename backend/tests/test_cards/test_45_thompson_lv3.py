"""Tests for .45 Thompson (Level 3)."""

import importlib

import pytest
from backend.engine.game import Game
from backend.models.enums import Action, CardType, ChaosTokenType, PlayerClass, SlotType
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)

_mod = importlib.import_module("backend.cards.rogue.45_thompson_lv3")
FortyFiveThompsonLv3 = _mod.FortyFiveThompsonLv3


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(combat=5)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)

    thompson = CardData(
        id="45_thompson_lv3", name=".45 Thompson", name_cn=".45汤姆逊冲锋枪",
        type=CardType.ASSET, card_class=PlayerClass.ROGUE, cost=5,
        slots=[SlotType.HAND, SlotType.HAND],
        traits=["item", "weapon", "firearm", "illicit"], uses={"ammo": 5},
    )
    g.register_card_data(thompson)

    g.register_card_data(make_enemy_data(id="enemy_a", fight=3, health=10))
    g.register_card_data(make_enemy_data(id="enemy_b", fight=4, health=10))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)

    g.card_registry.register_class(FortyFiveThompsonLv3)
    return g


def _equip(game):
    inv = game.state.get_investigator("inv1")
    instance_id = game.state.next_instance_id()
    inst = CardInstance(
        instance_id=instance_id, card_id="45_thompson_lv3",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND, SlotType.HAND], uses={"ammo": 5},
    )
    game.state.cards_in_play[instance_id] = inst
    inv.play_area.append(instance_id)
    game.card_registry.activate_card(
        "45_thompson_lv3", instance_id, game.event_bus,
        chaos_bag=game.chaos_bag)
    return instance_id


def _spawn(game, card_id, instance_id, engaged=True):
    enemy = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    inv = game.state.get_investigator("inv1")
    if engaged:
        inv.threat_area.append(instance_id)
    else:
        game.state.locations["test_location"].enemies.append(instance_id)
    return enemy


class TestFortyFiveThompsonLv3:
    def test_combat_bonus_and_damage(self, game):
        """+2战斗、+1伤害，命中扣1子弹。"""
        weapon_id = _equip(game)
        enemy = _spawn(game, "enemy_a", "enemy_1")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=weapon_id,
        )
        result = game.skill_test_engine._last_result
        assert result.modified_skill == 5 + 2
        assert enemy.damage == 2
        assert game.state.get_card_instance(weapon_id).uses["ammo"] == 4

    def test_spread_damage_to_other_enemy(self, game):
        """成功超出≥X（另一敌人攻击值）：花1子弹对其造成同等伤害。"""
        weapon_id = _equip(game)
        _spawn(game, "enemy_a", "enemy_1")  # 攻击目标，fight 3
        enemy_b = _spawn(game, "enemy_b", "enemy_2", engaged=False)  # fight 4
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=weapon_id,
        )
        # 5+2+0=7 vs 3 → 超出4 ≥ enemy_b fight 4 → 溅射 1+1=2 点
        assert enemy_b.damage == 2
        # 攻击1子弹 + 溅射1子弹
        assert game.state.get_card_instance(weapon_id).uses["ammo"] == 3

    def test_no_spread_when_margin_too_small(self, game):
        """超出不足另一敌人攻击值：无溅射、不额外耗弹。"""
        weapon_id = _equip(game)
        enemy_a = _spawn(game, "enemy_a", "enemy_1")
        enemy_b = _spawn(game, "enemy_b", "enemy_2", engaged=False)
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_1]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=weapon_id,
        )
        # 5+2-1=6 vs 3 → 超出3 < enemy_b fight 4 → 无溅射
        assert enemy_a.damage == 2
        assert enemy_b.damage == 0
        assert game.state.get_card_instance(weapon_id).uses["ammo"] == 4

    def test_no_ammo_cancels_attack(self, game):
        weapon_id = _equip(game)
        _spawn(game, "enemy_a", "enemy_1")
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
