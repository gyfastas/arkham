"""Tests for Roland's .38 Special — Roland Banks signature weapon."""

import pytest
from backend.cards.neutral.rolands_38_special import Rolands38Special
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

    gun_data = CardData(
        id="rolands_38_special", name="Roland's .38 Special", name_cn="罗兰的.38特种手枪",
        type=CardType.ASSET, card_class=PlayerClass.NEUTRAL, cost=3,
        slots=[SlotType.HAND], traits=["item", "weapon", "firearm"],
        uses={"ammo": 4}, unique=True,
    )
    g.register_card_data(gun_data)

    enemy_data = make_enemy_data(fight=5, health=6)
    g.register_card_data(enemy_data)

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)

    g.card_registry.register_class(Rolands38Special)
    return g


def _equip_gun(game):
    inv = game.state.get_investigator("inv1")
    instance_id = game.state.next_instance_id()
    card_inst = CardInstance(
        instance_id=instance_id, card_id="rolands_38_special",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND],
        uses={"ammo": 4},
    )
    game.state.cards_in_play[instance_id] = card_inst
    inv.play_area.append(instance_id)
    game.card_registry.activate_card("rolands_38_special", instance_id, game.event_bus)
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


class TestRolands38Special:
    def test_card_registered(self, game):
        assert "rolands_38_special" in game.card_registry.registered_cards

    def test_plus_one_combat_without_clues(self, game):
        """No clues at location: only +1 combat (3+1=4 vs fight 5 fails)."""
        gun_id = _equip_gun(game)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        game.state.get_location("test_location").clues = 0

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1",
            weapon_instance_id=gun_id,
        )
        assert enemy.damage == 0  # Attack failed

    def test_plus_three_combat_with_clues(self, game):
        """1+ clues at location: +3 combat instead (3+3=6 vs fight 5 succeeds),
        +1 damage, spends 1 ammo."""
        gun_id = _equip_gun(game)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        game.state.get_location("test_location").clues = 2

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1",
            weapon_instance_id=gun_id,
        )
        assert enemy.damage == 2  # 1 base + 1 bonus
        assert game.state.get_card_instance(gun_id).uses["ammo"] == 3

    def test_extra_damage_without_clues(self, game):
        """Successful attack without clues still deals +1 damage."""
        gun_id = _equip_gun(game)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]  # 3+1+1=5 vs 5 succeeds
        game.state.get_location("test_location").clues = 0

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1",
            weapon_instance_id=gun_id,
        )
        assert enemy.damage == 2

    def test_ammo_spent_even_on_miss(self, game):
        """卡面：花1弹药是攻击动作的费用——未命中同样消耗。"""
        gun_id = _equip_gun(game)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_2]  # 3+1-2=2 < 5 -> miss
        game.state.get_location("test_location").clues = 0

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1",
            weapon_instance_id=gun_id,
        )
        assert enemy.damage == 0  # 未命中无伤害
        assert game.state.get_card_instance(gun_id).uses["ammo"] == 3  # 弹药已扣
