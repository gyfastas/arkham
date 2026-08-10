"""Tests for Marksmanship (Level 1). (04104)

快速。启动枪械/远程支援的攻击能力时打出：可打连接地点目标，
无视冷漠/报复；对未交战敌人成功时+1伤害。
"""

import pytest
from backend.cards.guardian.marksmanship_lv1 import Marksmanship
from backend.engine.game import Game
from backend.models.enums import (
    Action, CardType, ChaosTokenType, PlayerClass, SlotType,
)
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_event_data,
    make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_asset_data(
        id="gun", name="Gun", cost=2, card_class=PlayerClass.GUARDIAN,
        slots=[SlotType.HAND], traits=["item", "weapon", "firearm"],
    ))
    g.register_card_data(make_event_data(
        id="marksmanship_lv1", name="Marksmanship", cost=2, fast=True,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(make_enemy_data(
        id="retaliator", name="R", fight=3, health=10, damage=2, horror=1,
        keywords=["retaliate"],
    ))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=0)
    g.card_registry.register_class(Marksmanship)

    inv = g.state.get_investigator("inv1")
    gun = CardInstance(
        instance_id="gun_1", card_id="gun", owner_id="inv1",
        controller_id="inv1", slot_used=[SlotType.HAND],
    )
    g.state.cards_in_play["gun_1"] = gun
    inv.play_area.append("gun_1")
    inv.hand.append("marksmanship_lv1")
    inv.resources = 3
    inv.actions_remaining = 3
    g.card_registry.activate_card("marksmanship_lv1", "mm_1", g.event_bus)
    return g


def _spawn_at_location(game, instance_id="enemy_1"):
    """敌人在地点上（未交战）。"""
    game.state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id="retaliator",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.get_location("test_location").enemies.append(instance_id)
    return game.state.cards_in_play[instance_id]


class TestMarksmanship:
    def test_bonus_damage_vs_unengaged(self, game):
        """对未交战敌人成功：+1伤害（基础1+1=2）。"""
        enemy = _spawn_at_location(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id="gun_1",
        )
        assert enemy.damage == 2
        inv = game.state.get_investigator("inv1")
        assert "marksmanship_lv1" in inv.discard
        assert inv.resources == 1  # 付了2费

    def test_ignores_retaliate_on_failure(self, game):
        """失败时无视报复：不受反击伤害。"""
        _spawn_at_location(game)
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_4]
        # 战斗 3-4 → 失败，报复(2伤害1恐惧)应被取消
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id="gun_1",
        )
        inv = game.state.get_investigator("inv1")
        assert inv.damage == 0
        assert inv.horror == 0

    def test_no_trigger_for_non_firearm(self, game):
        """近战武器攻击不触发。"""
        inv = game.state.get_investigator("inv1")
        game.state.card_database["gun"].traits = ["item", "weapon", "melee"]
        enemy = _spawn_at_location(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1", weapon_instance_id="gun_1",
        )
        assert enemy.damage == 1  # 无+1
        assert "marksmanship_lv1" in inv.hand  # 未打出
