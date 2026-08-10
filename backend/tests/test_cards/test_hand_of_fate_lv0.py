"""Tests for Hand of Fate (Level 0). (07020)

快速。敌人攻击你所在地点的调查员时打出：取消该次攻击，
向混乱袋加入等同敌人伤害值+恐惧值数量的祝福标记。
"""

import pytest
from backend.cards.guardian.hand_of_fate_lv0 import HandOfFate
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, PlayerClass
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_event_data(
        id="hand_of_fate_lv0", name="Hand of Fate", cost=3, fast=True,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(make_enemy_data(
        id="ghoul", name="Ghoul", fight=3, health=3, damage=1, horror=2))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=0)
    g.card_registry.register_class(HandOfFate)

    inv = g.state.get_investigator("inv1")
    inv.hand.append("hand_of_fate_lv0")
    inv.resources = 3
    g.card_registry.activate_card(
        "hand_of_fate_lv0", "hof_1", g.event_bus, chaos_bag=g.chaos_bag)
    return g


def _spawn_engaged(game, target_inv, instance_id="enemy_1"):
    game.state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.get_investigator(target_inv).threat_area.append(instance_id)


class TestHandOfFate:
    def test_cancels_attack_and_adds_bless(self, game):
        """攻击被取消；加入 伤害1+恐惧2=3 个祝福；付3费。"""
        _spawn_engaged(game, "inv1")
        inv = game.state.get_investigator("inv1")
        bless_before = game.chaos_bag.tokens.count(ChaosTokenType.BLESS)

        game.enemy_phase.resolve()

        assert inv.damage == 0 and inv.horror == 0  # 攻击被取消
        assert game.chaos_bag.tokens.count(ChaosTokenType.BLESS) == bless_before + 3
        assert inv.resources == 0
        assert "hand_of_fate_lv0" in inv.discard

    def test_not_played_when_cant_afford(self, game):
        """资源不足：不打出，攻击正常结算。"""
        _spawn_engaged(game, "inv1")
        inv = game.state.get_investigator("inv1")
        inv.resources = 2

        game.enemy_phase.resolve()

        assert inv.damage == 1 and inv.horror == 2
        assert "hand_of_fate_lv0" in inv.hand
