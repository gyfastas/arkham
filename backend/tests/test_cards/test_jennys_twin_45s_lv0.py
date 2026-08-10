"""Tests for Jenny's Twin .45s (Level 0) — Jenny Barnes signature weapon."""

import pytest
from backend.cards.neutral.jennys_twin_45s_lv0 import JennysTwin45s
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
        id="jennys_twin_45s_lv0", name="Jenny's Twin .45s", name_cn="珍妮的.45双枪",
        type=CardType.ASSET, card_class=PlayerClass.NEUTRAL, cost=0,
        slots=[SlotType.HAND, SlotType.HAND], traits=["item", "weapon", "firearm"],
        uses={"ammo": 4}, unique=True,
    )
    g.register_card_data(gun_data)

    enemy_data = make_enemy_data(fight=5, health=6)
    g.register_card_data(enemy_data)

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)

    g.card_registry.register_class(JennysTwin45s)
    return g


def _equip_guns(game):
    inv = game.state.get_investigator("inv1")
    instance_id = game.state.next_instance_id()
    card_inst = CardInstance(
        instance_id=instance_id, card_id="jennys_twin_45s_lv0",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND, SlotType.HAND],
        uses={"ammo": 4},
    )
    game.state.cards_in_play[instance_id] = card_inst
    inv.play_area.append(instance_id)
    game.card_registry.activate_card("jennys_twin_45s_lv0", instance_id, game.event_bus)
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


class TestJennysTwin45s:
    def test_card_registered(self, game):
        assert "jennys_twin_45s_lv0" in game.card_registry.registered_cards

    def test_combat_bonus_and_extra_damage(self, game):
        """+2 combat (3+2=5 vs fight 5) and +1 damage; spends 1 ammo."""
        gun_id = _equip_guns(game)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1",
            weapon_instance_id=gun_id,
        )
        # Without the +2 bonus (3 vs 5) the attack would fail
        assert enemy.damage == 2  # 1 base + 1 bonus
        assert game.state.get_card_instance(gun_id).uses["ammo"] == 3

    def test_no_bonus_without_ammo(self, game):
        """With no ammo, no combat bonus (attack fails) and no extra damage."""
        gun_id = _equip_guns(game)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        game.state.get_card_instance(gun_id).uses["ammo"] = 0

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1",
            weapon_instance_id=gun_id,
        )
        # 3 combat vs 5 fight -> fails, no damage, no ammo spent
        assert enemy.damage == 0
        assert game.state.get_card_instance(gun_id).uses["ammo"] == 0

    def test_ammo_spent_even_on_miss(self, game):
        """卡面：花1弹药是攻击动作的费用——未命中同样消耗。"""
        gun_id = _equip_guns(game)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_1]  # 3+2-1=4 < 5 -> miss

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1",
            weapon_instance_id=gun_id,
        )
        assert enemy.damage == 0  # 未命中无伤害
        assert game.state.get_card_instance(gun_id).uses["ammo"] == 3  # 弹药已扣
