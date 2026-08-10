"""Tests for Colt Vest Pocket (Level 0)."""

import pytest
from backend.cards.rogue.colt_vest_pocket_lv0 import ColtVestPocket
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import Action, CardType, ChaosTokenType, GameEvent, PlayerClass, SlotType
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
    loc = make_location_data()
    g.register_card_data(loc)

    colt = CardData(
        id="colt_vest_pocket_lv0", name="Colt Vest Pocket", name_cn="柯尔特袖珍手枪",
        type=CardType.ASSET, card_class=PlayerClass.ROGUE, cost=2,
        slots=[SlotType.HAND], traits=["item", "weapon", "firearm", "illicit"],
        uses={"ammo": 5},
    )
    g.register_card_data(colt)
    g.register_card_data(make_enemy_data(fight=3, health=5))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)

    g.card_registry.register_class(ColtVestPocket)
    return g


def _equip(game):
    inv = game.state.get_investigator("inv1")
    instance_id = game.state.next_instance_id()
    inst = CardInstance(
        instance_id=instance_id, card_id="colt_vest_pocket_lv0",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND], uses={"ammo": 5},
    )
    game.state.cards_in_play[instance_id] = inst
    inv.play_area.append(instance_id)
    game.card_registry.activate_card(
        "colt_vest_pocket_lv0", instance_id, game.event_bus,
        chaos_bag=game.chaos_bag)
    return instance_id


def _spawn_enemy(game):
    enemy = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play["enemy_1"] = enemy
    game.state.get_investigator("inv1").threat_area.append("enemy_1")
    return enemy


class TestColtVestPocket:
    def test_fight_bonus_and_damage(self, game):
        """+1战斗、+1伤害，命中扣1子弹。"""
        weapon_id = _equip(game)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=weapon_id,
        )
        result = game.skill_test_engine._last_result
        assert result.modified_skill == 4 + 1
        assert enemy.damage == 2
        assert game.state.get_card_instance(weapon_id).uses["ammo"] == 4

    def test_discarded_at_round_end(self, game):
        """强制：本轮结束时丢弃（离场、入弃牌堆、释放槽位）。"""
        weapon_id = _equip(game)
        inv = game.state.get_investigator("inv1")
        game.event_bus.emit(EventContext(
            game_state=game.state,
            event=GameEvent.ROUND_ENDS,
        ))
        assert game.state.get_card_instance(weapon_id) is None
        assert weapon_id not in inv.play_area
        assert "colt_vest_pocket_lv0" in inv.discard

    def test_no_ammo_cancels_attack(self, game):
        weapon_id = _equip(game)
        _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        game.state.get_card_instance(weapon_id).uses["ammo"] = 0

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3
        ok = game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id=weapon_id,
        )
        assert ok is False
        assert inv.actions_remaining == 3
