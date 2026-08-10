"""Tests for Finn's Trusty .38 (Level 0)."""

import pytest
from backend.cards.neutral.finns_trusty_38_lv0 import FinnsTrusty38
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data(combat=4))
    g.register_card_data(make_location_data())
    g.register_card_data(make_asset_data(
        id="finns_trusty_38_lv0", name="Finn's Trusty .38", cost=2,
        uses={"ammo": 3},
    ))
    g.register_card_data(make_enemy_data(
        id="ghoul", name="Ghoul", fight=2, health=5, evade=2,
    ))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(FinnsTrusty38)
    inv = g.state.get_investigator("inv1")
    inv.hand.append("finns_trusty_38_lv0")
    inv.resources = 5
    # 固定袋中只有 0，检定结果可预期（4+2 vs 2 必中）
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]
    return g


def _play(game):
    game.action_resolver.perform_action(
        "inv1", Action.PLAY, card_id="finns_trusty_38_lv0",
    )
    return next(
        i for i in game.card_registry.active_instances.values()
        if isinstance(i, FinnsTrusty38)
    )


def _spawn(game, engaged=False, instance_id="enemy_1"):
    enemy = CardInstance(
        instance_id=instance_id, card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    if engaged:
        game.state.get_investigator("inv1").threat_area.append(instance_id)
    else:
        game.state.get_location("test_location").enemies.append(instance_id)
    return enemy


class TestFinnsTrusty38:
    def test_ammo_spent_and_combat_bonus(self, game):
        """攻击花费1弹药并+2战斗。"""
        impl = _play(game)
        inst = game.state.get_card_instance(impl.instance_id)
        _spawn(game, engaged=True)
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
            weapon_instance_id=impl.instance_id,
        )
        assert inst.uses["ammo"] == 2

    def test_bonus_damage_vs_unengaged_enemy(self, game):
        """攻击未交战敌人：+1伤害（1基础+1=2）。"""
        impl = _play(game)
        enemy = _spawn(game, engaged=False)
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
            weapon_instance_id=impl.instance_id,
        )
        assert enemy.damage == 2

    def test_no_bonus_damage_vs_engaged_enemy(self, game):
        """攻击已交战敌人：无+1伤害（仅1基础伤害）。"""
        impl = _play(game)
        enemy = _spawn(game, engaged=True)
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
            weapon_instance_id=impl.instance_id,
        )
        assert enemy.damage == 1
