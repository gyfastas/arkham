"""Tests for Old Hunting Rifle (Level 3)."""

import pytest
from backend.cards.survivor.old_hunting_rifle_lv3 import OldHuntingRifle
from backend.models.enums import Action, ChaosTokenType, PlayerClass, Skill, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
    make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="old_hunting_rifle_lv3", name="Old Hunting Rifle", cost=3,
        card_class=PlayerClass.SURVIVOR, slots=[SlotType.HAND, SlotType.HAND],
        traits=["item", "weapon", "firearm"], uses={"ammo": 3},
    ))
    g.register_card_data(make_enemy_data(fight=3, health=10, evade=3))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(OldHuntingRifle)
    return g


def _equip_rifle(game):
    inv = game.state.get_investigator("inv1")
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id="old_hunting_rifle_lv3",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND, SlotType.HAND], uses={"ammo": 3},
    )
    inv.play_area.append(iid)
    game.card_registry.activate_card(
        "old_hunting_rifle_lv3", iid, game.event_bus)
    return iid


def _spawn_enemy(game):
    game.state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.get_investigator("inv1").threat_area.append("enemy_1")
    return game.state.cards_in_play["enemy_1"]


def _fight(game, rifle_id, token):
    inv = game.state.get_investigator("inv1")
    inv.actions_remaining = 3
    game.chaos_bag.tokens = [token]
    ok = game.action_resolver.perform_action(
        "inv1", Action.FIGHT,
        enemy_instance_id="enemy_1", weapon_instance_id=rifle_id,
    )
    return ok, game.skill_test_engine._last_result


class TestOldHuntingRifle:
    def test_card_registered(self, game):
        assert "old_hunting_rifle_lv3" in game.card_registry.registered_cards

    def test_attack_bonus_and_damage(self, game):
        """花1弹药：+3战斗、+2伤害。"""
        rifle_id = _equip_rifle(game)
        enemy = _spawn_enemy(game)

        ok, result = _fight(game, rifle_id, ChaosTokenType.ZERO)

        assert ok is True
        assert result.modified_skill == 6  # 3 + 3
        assert result.success is True
        assert enemy.damage == 3  # 基础1 + 2
        inst = game.state.get_card_instance(rifle_id)
        assert inst.uses["ammo"] == 2

    def test_skull_jams_and_auto_fails(self, game):
        """揭示骷髅：攻击自动失败并卡壳；卡壳后无法启动，排除后方可再用。"""
        rifle_id = _equip_rifle(game)
        _spawn_enemy(game)
        impl = game.card_registry.active_instances[rifle_id]

        ok, result = _fight(game, rifle_id, ChaosTokenType.SKULL)
        assert ok is True  # 行动已执行
        assert result.success is False  # 自动失败
        assert impl._jammed is True

        # 卡壳中：攻击被取消（行动不消耗、弹药不扣）
        inv = game.state.get_investigator("inv1")
        ammo_before = game.state.get_card_instance(rifle_id).uses["ammo"]
        ok2, _ = _fight(game, rifle_id, ChaosTokenType.ZERO)
        assert ok2 is False
        assert game.state.get_card_instance(rifle_id).uses["ammo"] == ammo_before

        # 排除卡壳后恢复
        assert impl.clear_jam(game.state, "inv1") is True
        ok3, result3 = _fight(game, rifle_id, ChaosTokenType.ZERO)
        assert ok3 is True
        assert result3.success is True

    def test_no_ammo_cancels_attack(self, game):
        rifle_id = _equip_rifle(game)
        _spawn_enemy(game)
        game.state.get_card_instance(rifle_id).uses["ammo"] = 0

        ok, _ = _fight(game, rifle_id, ChaosTokenType.ZERO)
        assert ok is False
