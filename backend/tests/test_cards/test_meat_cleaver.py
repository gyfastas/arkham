"""Tests for Meat Cleaver (Level 0)."""

import pytest
from backend.cards.survivor.meat_cleaver_lv0 import MeatCleaver
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
    inv_data = make_investigator_data(combat=3, sanity=7)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="meat_cleaver_lv0", name="Meat Cleaver", cost=3,
        card_class=PlayerClass.SURVIVOR, slots=[SlotType.HAND],
        traits=["item", "weapon", "melee"],
    ))
    g.register_card_data(make_enemy_data(fight=3, health=10, evade=3))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(MeatCleaver)
    return g


def _equip_cleaver(game):
    inv = game.state.get_investigator("inv1")
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id="meat_cleaver_lv0",
        owner_id="inv1", controller_id="inv1", slot_used=[SlotType.HAND],
    )
    inv.play_area.append(iid)
    game.card_registry.activate_card("meat_cleaver_lv0", iid, game.event_bus)
    return iid


def _spawn_enemy(game, health=10):
    game.state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.get_card_data("test_enemy").enemy_health = health
    game.state.get_investigator("inv1").threat_area.append("enemy_1")
    return game.state.cards_in_play["enemy_1"]


def _fight(game, weapon_id, token=ChaosTokenType.ZERO):
    inv = game.state.get_investigator("inv1")
    inv.actions_remaining = 3
    game.chaos_bag.tokens = [token]
    game.action_resolver.perform_action(
        "inv1", Action.FIGHT,
        enemy_instance_id="enemy_1", weapon_instance_id=weapon_id,
    )
    return game.skill_test_engine._last_result


class TestMeatCleaver:
    def test_card_registered(self, game):
        assert "meat_cleaver_lv0" in game.card_registry.registered_cards

    def test_plus_1_combat_normal(self, game):
        cleaver_id = _equip_cleaver(game)
        _spawn_enemy(game)
        result = _fight(game, cleaver_id)
        assert result.modified_skill == 4  # 3 + 1

    def test_plus_2_combat_at_low_sanity(self, game):
        """剩余理智≤3时 +2 战斗。"""
        cleaver_id = _equip_cleaver(game)
        _spawn_enemy(game)
        inv = game.state.get_investigator("inv1")
        inv.horror = 4  # 理智7-4=3

        result = _fight(game, cleaver_id)
        assert result.modified_skill == 5  # 3 + 2

    def test_empower_bonus_damage(self, game):
        """附加费用：承受1恐惧，本次攻击+1伤害。"""
        cleaver_id = _equip_cleaver(game)
        enemy = _spawn_enemy(game)
        inv = game.state.get_investigator("inv1")
        impl = game.card_registry.active_instances[cleaver_id]

        assert impl.empower(game.state, "inv1") is True
        assert inv.horror == 1

        result = _fight(game, cleaver_id)
        assert result.success is True
        assert enemy.damage == 2  # 基础1 + 附加1

    def test_defeat_heals_horror(self, game):
        """本次攻击击败敌人：治愈1点恐惧。"""
        cleaver_id = _equip_cleaver(game)
        _spawn_enemy(game, health=1)
        inv = game.state.get_investigator("inv1")
        inv.horror = 2

        result = _fight(game, cleaver_id)
        assert result.success is True
        assert "enemy_1" not in game.state.cards_in_play  # 被击败
        assert inv.horror == 1  # 治愈1点
