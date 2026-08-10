"""Tests for Baseball Bat (Level 0)."""

import pytest
from backend.cards.survivor.baseball_bat_lv0 import BaseballBat
from backend.models.enums import Action, ChaosTokenType, PlayerClass, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_asset_data, make_location_data,
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

    bat_data = make_asset_data(
        id="baseball_bat_lv0", name="Baseball Bat", cost=2,
        card_class=PlayerClass.SURVIVOR,
        slots=[SlotType.HAND, SlotType.HAND],
        traits=["item", "weapon", "melee"],
    )
    g.register_card_data(bat_data)
    g.register_card_data(make_enemy_data(fight=3, health=10, evade=3))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(BaseballBat)
    return g


def _equip_bat(game):
    inv = game.state.get_investigator("inv1")
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id="baseball_bat_lv0",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND, SlotType.HAND],
    )
    inv.play_area.append(iid)
    game.card_registry.activate_card("baseball_bat_lv0", iid, game.event_bus)
    return iid


def _spawn_enemy(game):
    game.state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.get_investigator("inv1").threat_area.append("enemy_1")
    return game.state.cards_in_play["enemy_1"]


def _fight(game, bat_id, token):
    inv = game.state.get_investigator("inv1")
    inv.actions_remaining = 3
    game.chaos_bag.tokens = [token]
    game.action_resolver.perform_action(
        "inv1", Action.FIGHT,
        enemy_instance_id="enemy_1",
        weapon_instance_id=bat_id,
    )


class TestBaseballBat:
    def test_card_registered(self, game):
        assert "baseball_bat_lv0" in game.card_registry.registered_cards

    def test_takes_two_hand_slots(self, game):
        bat_data = game.state.card_database["baseball_bat_lv0"]
        assert bat_data.slots == [SlotType.HAND, SlotType.HAND]

    def test_combat_bonus_and_bonus_damage(self, game):
        """+2战斗、+1伤害：3+2+0=5 vs 3 成功，造成 1+1=2 伤害。"""
        bat_id = _equip_bat(game)
        enemy = _spawn_enemy(game)
        _fight(game, bat_id, ChaosTokenType.ZERO)

        result = game.skill_test_engine._last_result
        assert result.modified_skill == 5
        assert result.success is True
        assert enemy.damage == 2

    def test_discard_after_attack_on_skull(self, game):
        """揭示骷髅：攻击结算后弃置球棒（即使成功）。"""
        bat_id = _equip_bat(game)
        _spawn_enemy(game)
        _fight(game, bat_id, ChaosTokenType.SKULL)

        inv = game.state.get_investigator("inv1")
        assert bat_id not in inv.play_area
        assert "baseball_bat_lv0" in inv.discard

    def test_discard_after_attack_on_auto_fail(self, game):
        """揭示自动失败：攻击失败，结算后仍弃置球棒。"""
        bat_id = _equip_bat(game)
        enemy = _spawn_enemy(game)
        _fight(game, bat_id, ChaosTokenType.AUTO_FAIL)

        inv = game.state.get_investigator("inv1")
        assert enemy.damage == 0
        assert bat_id not in inv.play_area
        assert "baseball_bat_lv0" in inv.discard

    def test_no_discard_on_cultist(self, game):
        """仅骷髅/自动失败弃置：cultist 不弃置。"""
        bat_id = _equip_bat(game)
        _spawn_enemy(game)
        _fight(game, bat_id, ChaosTokenType.CULTIST)

        inv = game.state.get_investigator("inv1")
        assert bat_id in inv.play_area

    def test_no_bonus_when_not_used(self, game):
        """不用球棒的攻击无加值。"""
        _equip_bat(game)
        enemy = _spawn_enemy(game)
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
        )
        result = game.skill_test_engine._last_result
        assert result.modified_skill == 3
        assert enemy.damage == 1
