"""Tests for Ornate Bow (Level 3)."""

import pytest

from backend.cards.neutral.ornate_bow_lv3 import OrnateBow
from backend.models.enums import Action, ChaosTokenType, CardType, PlayerClass, Skill
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import make_enemy_data, make_investigator_data, make_location_data
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(combat=3, agility=5)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    bow_data = CardData(
        id="ornate_bow_lv3", name="Ornate Bow", name_cn="华丽长弓",
        type=CardType.ASSET, card_class=PlayerClass.NEUTRAL, cost=4,
        traits=["item", "relic", "weapon", "ranged"],
        skill_icons={"combat": 1, "agility": 1},
        uses={"ammo": 1},
    )
    g.register_card_data(bow_data)
    enemy_data = make_enemy_data(fight=3, health=10)
    g.register_card_data(enemy_data)

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=2)
    g.card_registry.register_class(OrnateBow)
    return g


def _equip_bow(game):
    inv = game.state.get_investigator("inv1")
    card_inst = CardInstance(
        instance_id="bow_1", card_id="ornate_bow_lv3",
        owner_id="inv1", controller_id="inv1",
    )
    card_inst.uses = {"ammo": 1}
    game.state.cards_in_play["bow_1"] = card_inst
    inv.play_area.append("bow_1")
    game.card_registry.activate_card("ornate_bow_lv3", "bow_1", game.event_bus)
    return "bow_1"


def _spawn_enemy(game):
    enemy = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play["enemy_1"] = enemy
    game.state.get_investigator("inv1").threat_area.append("enemy_1")
    return enemy


class TestOrnateBow:
    def test_attack_uses_agility_and_bonus_damage(self, game):
        """攻击用敏捷代替战斗：5敏+2 vs 战斗3，+2伤害，消耗1弹药。"""
        _equip_bow(game)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        ok = game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id="bow_1",
        )
        assert ok is True
        # 敏捷5 + 2 = 7 vs 战斗3 → 成功；伤害 1 + 2 = 3
        assert enemy.damage == 3
        bow = game.state.get_card_instance("bow_1")
        assert bow.uses["ammo"] == 0

    def test_no_ammo_cancels_attack(self, game):
        """无弹药：不能以本弓发起攻击（动作不消耗）。"""
        _equip_bow(game)
        enemy = _spawn_enemy(game)
        bow = game.state.get_card_instance("bow_1")
        bow.uses["ammo"] = 0
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        ok = game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id="bow_1",
        )
        assert ok is False
        assert enemy.damage == 0
        assert inv.actions_remaining == 3

    def test_reload_places_ammo(self, game):
        """[行动]装填：放置1弹药（至多1）。"""
        _equip_bow(game)
        bow = game.state.get_card_instance("bow_1")
        bow.uses["ammo"] = 0
        impl = game.card_registry.active_instances["bow_1"]

        assert impl.activate_reload(game.state, "inv1") is True
        assert bow.uses["ammo"] == 1
        # 已有1弹药时不能再装
        assert impl.activate_reload(game.state, "inv1") is False
        assert bow.uses["ammo"] == 1
