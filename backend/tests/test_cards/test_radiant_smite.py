"""Tests for Radiant Smite (Level 1). (07153)

攻击：发动时封印袋中至多3个祝福；每个封印+1技能值+1伤害；意志高于战斗时
改用意志。击败目标则封印标记返回供应堆，否则释放回袋。
"""

import pytest

from backend.cards.guardian.radiant_smite_lv1 import RadiantSmite
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, PlayerClass
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


def _game(enemy_health):
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(willpower=5, combat=2)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="radiant_smite_lv1", name="Radiant Smite", cost=1,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(make_enemy_data(id="ghoul", fight=3, health=enemy_health))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(RadiantSmite)

    enemy = CardInstance(
        instance_id="enemy_1", card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    g.state.cards_in_play["enemy_1"] = enemy
    g.state.get_investigator("inv1").threat_area.append("enemy_1")

    # 袋中3个祝福 + 1个+1（封印后攻击必中：意志5+3封印+1标记 vs 战斗3）
    g.chaos_bag.tokens = [
        ChaosTokenType.BLESS, ChaosTokenType.BLESS, ChaosTokenType.BLESS,
        ChaosTokenType.PLUS_1,
    ]

    inv = g.state.get_investigator("inv1")
    inv.hand.append("radiant_smite_lv1")
    inv.actions_remaining = 3
    return g


def _bless_in(lst):
    return sum(1 for t in lst if t == ChaosTokenType.BLESS)


class TestRadiantSmite:
    def test_defeat_returns_tokens_to_pool(self):
        """击败目标：3祝福封印提供+3技能/+3伤害，击败后返回供应堆（不回袋）。"""
        game = _game(enemy_health=4)
        inv = game.state.get_investigator("inv1")

        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="radiant_smite_lv1",
        )
        # 3个祝福被封印出袋
        assert _bless_in(game.chaos_bag.sealed) == 3
        assert _bless_in(game.chaos_bag.tokens) == 0

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
        )
        # 意志5 + 3封印 + 1标记 = 9 vs 3 成功；伤害 1+3=4 击败
        assert game.state.get_card_instance("enemy_1") is None
        # 封印标记返回供应堆：既不在袋中也不在封印区
        assert _bless_in(game.chaos_bag.sealed) == 0
        assert _bless_in(game.chaos_bag.tokens) == 0

    def test_no_defeat_releases_tokens(self):
        """未击败目标：封印的祝福释放回混乱袋。"""
        game = _game(enemy_health=10)

        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="radiant_smite_lv1",
        )
        assert _bless_in(game.chaos_bag.sealed) == 3

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1",
        )
        enemy = game.state.get_card_instance("enemy_1")
        assert enemy is not None
        assert enemy.damage == 4  # 1基础 + 3封印
        # 未击败：3个祝福释放回袋
        assert _bless_in(game.chaos_bag.sealed) == 0
        assert _bless_in(game.chaos_bag.tokens) == 3
