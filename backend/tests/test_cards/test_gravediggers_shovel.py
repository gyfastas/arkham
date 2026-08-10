"""Tests for Gravedigger's Shovel (Level 0)."""

import pytest
from backend.cards.survivor.gravediggers_shovel_lv0 import GravediggersShovel
from backend.models.enums import Action, ChaosTokenType, GameEvent, PlayerClass, Skill, SlotType
from backend.engine.event_bus import EventContext
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data, make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    loc = make_location_data(clue_value=3)
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="gravediggers_shovel_lv0", name="Gravedigger's Shovel", cost=2,
        card_class=PlayerClass.SURVIVOR, slots=[SlotType.HAND],
        traits=["item", "tool", "weapon", "melee"],
    ))
    g.register_card_data(make_enemy_data(fight=4, health=5))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=3)
    g.card_registry.register_class(GravediggersShovel)
    return g


def _put_in_play(game):
    inv = game.state.get_investigator("inv1")
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id="gravediggers_shovel_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    inv.play_area.append(iid)
    impl = game.card_registry.activate_card(
        "gravediggers_shovel_lv0", iid, game.event_bus,
        chaos_bag=game.chaos_bag)
    return iid, impl


def _add_enemy(game, engaged=True):
    enemy = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play["enemy_1"] = enemy
    if engaged:
        game.state.get_investigator("inv1").threat_area.append("enemy_1")
    else:
        game.state.locations["test_location"].enemies.append("enemy_1")
    return enemy


class TestGravediggersShovel:
    def test_card_registered(self, game):
        assert "gravediggers_shovel_lv0" in game.card_registry.registered_cards

    def test_fight_gets_plus_2_combat(self, game):
        """以铲子攻击+2战斗：战斗3+2=5 对 战斗值4，0标记命中。"""
        shovel_id, _ = _put_in_play(game)
        _add_enemy(game)
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        ok = game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
            weapon_instance_id=shovel_id)
        assert ok is True
        result = game.skill_test_engine._last_result
        assert result.success is True  # 3+2+0=5 >= 4
        assert any(m["reason"] == "gravediggers_shovel_combat"
                   for m in result.extra["skill_bonus_sources"])

    def test_no_bonus_without_shovel_source(self, game):
        """徒手攻击（source 非铲子）不享受+2。"""
        _put_in_play(game)
        _add_enemy(game)
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1")
        result = game.skill_test_engine._last_result
        assert result.success is False  # 3+0 < 4

    def test_discard_discovers_clue(self, game):
        """[action] 丢弃铲子：发现所在地点1个线索。"""
        shovel_id, impl = _put_in_play(game)
        inv = game.state.get_investigator("inv1")
        loc = game.state.locations["test_location"]

        assert impl.activate_discover_clue(game.state, "inv1") is True
        assert inv.clues == 1
        assert loc.clues == 2
        assert shovel_id not in inv.play_area
        assert "gravediggers_shovel_lv0" in inv.discard
        assert game.state.get_card_instance(shovel_id) is None

    def test_discover_clue_fails_without_clues(self, game):
        """地点无线索时不能启动，铲子留在场上。"""
        shovel_id, impl = _put_in_play(game)
        inv = game.state.get_investigator("inv1")
        game.state.locations["test_location"].clues = 0

        assert impl.activate_discover_clue(game.state, "inv1") is False
        assert shovel_id in inv.play_area
        assert inv.clues == 0
