"""Tests for Flamethrower (Level 5). (04305)

[行动]花费1弹药：攻击（目标必须是交战敌人中战斗值最高者），+4战斗；
成功时不造成标准伤害，改为在交战敌人间分配至多4点伤害。
"""

import pytest
from backend.cards.guardian.flamethrower_lv5 import Flamethrower
from backend.engine.game import Game
from backend.models.enums import (
    Action, CardType, ChaosTokenType, PlayerClass, SlotType,
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
        id="flamethrower_lv5", name="Flamethrower", name_cn="火焰喷射器",
        type=CardType.ASSET, card_class=PlayerClass.GUARDIAN, cost=4,
        slots=[SlotType.BODY, SlotType.HAND, SlotType.HAND],
        traits=["item", "weapon", "firearm"], uses={"ammo": 4},
    ))
    g.register_card_data(make_enemy_data(
        id="weak_enemy", name="Weak", fight=2, health=2))
    g.register_card_data(make_enemy_data(
        id="strong_enemy", name="Strong", fight=3, health=5))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=0)
    g.card_registry.register_class(Flamethrower)
    return g


def _equip(game):
    inv = game.state.get_investigator("inv1")
    instance_id = game.state.next_instance_id()
    game.state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id="flamethrower_lv5",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.BODY, SlotType.HAND], uses={"ammo": 4},
    )
    inv.play_area.append(instance_id)
    game.card_registry.activate_card(
        "flamethrower_lv5", instance_id, game.event_bus)
    inv.actions_remaining = 3
    return instance_id


def _spawn(game, card_id, instance_id):
    game.state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    game.state.get_investigator("inv1").threat_area.append(instance_id)
    return game.state.cards_in_play[instance_id]


class TestFlamethrower:
    def test_spread_damage_among_engaged(self, game):
        """成功：4点伤害在交战敌人间分配（自动先填满被攻击敌人）。"""
        weapon = _equip(game)
        weak = _spawn(game, "weak_enemy", "enemy_1")    # 战斗2 生命2
        strong = _spawn(game, "strong_enemy", "enemy_2")  # 战斗3 生命5
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]

        # 必须打战斗值最高的 strong（3 > 2）
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_2", weapon_instance_id=weapon,
        )
        # 4点伤害：strong 生命5 → 全吃4点；weak 不受伤害
        assert strong.damage == 4
        assert weak.damage == 0
        assert game.state.get_card_instance(weapon).uses["ammo"] == 3

    def test_spread_after_kill(self, game):
        """被攻击敌人生命较低时，剩余伤害分配给其他交战敌人。"""
        weapon = _equip(game)
        _spawn(game, "strong_enemy", "enemy_2")  # 战斗3 生命5
        weak2 = _spawn(game, "weak_enemy", "enemy_3")  # 战斗2 生命2
        # 提高 weak_enemy 战斗值使其成为最高档？不行——直接给 strong 降生命
        game.state.card_database["strong_enemy"].enemy_health = 2
        strong = game.state.get_card_instance("enemy_2")
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_2", weapon_instance_id=weapon,
        )
        # strong 生命2：2点击杀它，剩余2点分给 weak2
        assert "enemy_2" not in game.state.cards_in_play  # 被击败离场
        assert weak2.damage == 2

    def test_must_target_highest_fight(self, game):
        """目标不是最高战斗值敌人：攻击被取消，不耗弹药。"""
        weapon = _equip(game)
        weak = _spawn(game, "weak_enemy", "enemy_1")
        _spawn(game, "strong_enemy", "enemy_2")
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]

        result = game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=weapon,
        )
        assert result is False  # 攻击被取消，行动未消耗
        assert weak.damage == 0
        assert game.state.get_card_instance(weapon).uses["ammo"] == 4

    def test_no_ammo_cancels(self, game):
        """没有弹药：无法以本卡攻击。"""
        weapon = _equip(game)
        game.state.get_card_instance(weapon).uses["ammo"] = 0
        strong = _spawn(game, "strong_enemy", "enemy_2")
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]

        result = game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_2", weapon_instance_id=weapon,
        )
        assert result is False
        assert strong.damage == 0
