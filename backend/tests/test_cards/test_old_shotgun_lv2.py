"""Tests for Old Shotgun (Level 2). (08088)

[行动]花费1弹药：攻击，+3战斗；伤害替换为成功超出点数（1-3）。
"""

import pytest
from backend.cards.guardian.old_shotgun_lv2 import OldShotgun
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

    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(CardData(
        id="old_shotgun_lv2", name="Old Shotgun", name_cn="旧霰弹枪",
        type=CardType.ASSET, card_class=PlayerClass.GUARDIAN, cost=0,
        slots=[SlotType.HAND, SlotType.HAND],
        traits=["item", "weapon", "firearm"], uses={"ammo": 0},
    ))
    g.register_card_data(make_enemy_data(fight=3, health=10))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=0)
    g.card_registry.register_class(OldShotgun)
    return g


def _setup(game, ammo):
    inv = game.state.get_investigator("inv1")
    weapon = game.state.next_instance_id()
    game.state.cards_in_play[weapon] = CardInstance(
        instance_id=weapon, card_id="old_shotgun_lv2",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND, SlotType.HAND], uses={"ammo": ammo},
    )
    inv.play_area.append(weapon)
    game.card_registry.activate_card(
        "old_shotgun_lv2", weapon, game.event_bus)
    game.state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    inv.threat_area.append("enemy_1")
    inv.actions_remaining = 3
    return weapon


class TestOldShotgun:
    def test_damage_equals_succeed_by_capped_3(self, game):
        """成功超出4点：伤害封顶3（消耗1弹药）。"""
        weapon = _setup(game, ammo=1)
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]
        # 战斗 3+3+1=7 vs 3 → 超出4 → 封顶3
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=weapon,
        )
        enemy = game.state.get_card_instance("enemy_1")
        assert enemy.damage == 3
        assert game.state.get_card_instance(weapon).uses["ammo"] == 0

    def test_damage_minimum_1(self, game):
        """恰好命中（超出0点）：伤害下限1。"""
        weapon = _setup(game, ammo=2)
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_3]
        # 战斗 3+3-3=3 vs 3 → 超出0 → 下限1
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=weapon,
        )
        enemy = game.state.get_card_instance("enemy_1")
        assert enemy.damage == 1

    def test_no_ammo_no_bonus(self, game):
        """0弹药：无+3战斗、无伤害替换（等同徒手）。"""
        weapon = _setup(game, ammo=0)
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]
        # 战斗 3+1=4 vs 3 → 成功，标准伤害1
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=weapon,
        )
        enemy = game.state.get_card_instance("enemy_1")
        assert enemy.damage == 1
