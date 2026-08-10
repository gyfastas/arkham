"""Tests for Shotgun (Level 4)."""

import pytest
from backend.cards.guardian.shotgun_lv4 import Shotgun
from backend.engine.game import Game
from backend.models.enums import Action, CardType, ChaosTokenType, PlayerClass, SlotType
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import make_enemy_data, make_investigator_data, make_location_data


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)

    loc = make_location_data()
    g.register_card_data(loc)

    shotgun_data = CardData(
        id="shotgun_lv4", name="Shotgun", name_cn="霰弹枪",
        type=CardType.ASSET, card_class=PlayerClass.GUARDIAN, cost=5,
        slots=[SlotType.HAND, SlotType.HAND], traits=["item", "weapon", "firearm"],
        uses={"ammo": 2},
    )
    g.register_card_data(shotgun_data)

    enemy_data = make_enemy_data(fight=3, health=10)
    g.register_card_data(enemy_data)

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)

    g.card_registry.register_class(Shotgun)
    return g


def _equip_shotgun(game, ammo=2):
    inv = game.state.get_investigator("inv1")
    instance_id = game.state.next_instance_id()
    card_inst = CardInstance(
        instance_id=instance_id, card_id="shotgun_lv4",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND, SlotType.HAND],
        uses={"ammo": ammo},
    )
    game.state.cards_in_play[instance_id] = card_inst
    inv.play_area.append(instance_id)
    game.card_registry.activate_card("shotgun_lv4", instance_id, game.event_bus)
    return instance_id


def _spawn_enemy(game):
    enemy = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play["enemy_1"] = enemy
    inv = game.state.get_investigator("inv1")
    inv.threat_area.append("enemy_1")
    return enemy


def _fight(game, weapon_id):
    inv = game.state.get_investigator("inv1")
    inv.actions_remaining = 3
    game.action_resolver.perform_action(
        "inv1", Action.FIGHT,
        enemy_instance_id="enemy_1",
        weapon_instance_id=weapon_id,
    )


class TestShotgun:
    def test_card_registered(self, game):
        assert "shotgun_lv4" in game.card_registry.registered_cards

    def test_combat_bonus_and_margin_damage(self, game):
        """+3战斗；伤害=成功超出点数（3+3+0 vs 3 → 超3点 → 3伤害）。"""
        shotgun_id = _equip_shotgun(game)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        _fight(game, shotgun_id)
        assert enemy.damage == 3
        card = game.state.get_card_instance(shotgun_id)
        assert card.uses["ammo"] == 1  # 命中扣1弹药

    def test_damage_capped_at_5(self, game):
        """超出点数超过5时伤害封顶为5。"""
        shotgun_id = _equip_shotgun(game)
        enemy = _spawn_enemy(game)
        # 战斗3 + 霰弹枪3 + token+1 = 7？不够，直接拉高调查员战斗
        inv = game.state.get_investigator("inv1")
        inv.card_data.skills.combat = 8
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]
        # 8 + 3 + 1 = 12 vs 3 → 超9点 → 封顶5

        _fight(game, shotgun_id)
        assert enemy.damage == 5

    def test_minimum_1_damage_on_exact_success(self, game):
        """恰好等于难度也算成功：伤害下限1。"""
        shotgun_id = _equip_shotgun(game)
        enemy = _spawn_enemy(game)
        # 战斗3 + 霰弹枪3 = 6 vs 难度6 → 超0点 → 下限1
        enemy_data = game.state.get_card_data("test_enemy")
        enemy_data.enemy_fight = 6
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        _fight(game, shotgun_id)
        assert enemy.damage == 1

    def test_no_ammo_no_bonus(self, game):
        """无弹药：+3不生效，伤害为徒手基础1，不扣弹药。"""
        shotgun_id = _equip_shotgun(game, ammo=0)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]
        # 战斗3 + 1 = 4 vs 3 → 成功，但无弹药 → 仅基础1伤害

        _fight(game, shotgun_id)
        assert enemy.damage == 1
        card = game.state.get_card_instance(shotgun_id)
        assert card.uses["ammo"] == 0

    def test_miss_no_ammo_spent(self, game):
        """失手不扣弹药（简化为命中扣费）。"""
        shotgun_id = _equip_shotgun(game)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]

        _fight(game, shotgun_id)
        assert enemy.damage == 0
        card = game.state.get_card_instance(shotgun_id)
        assert card.uses["ammo"] == 2
