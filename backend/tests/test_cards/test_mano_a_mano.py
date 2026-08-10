"""Tests for Mano a Mano (Level 1). (03229)

只可作为你的第一个行动打出。对与你交战的一个敌人造成1点伤害。
此行动不会引起趁乱攻击。
"""

import pytest
from backend.cards.guardian.mano_a_mano_lv1 import ManoAMano
from backend.engine.game import Game
from backend.models.enums import Action, PlayerClass
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
        id="mano_a_mano_lv1", name="Mano a Mano", cost=0,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(make_enemy_data(
        id="rat", name="Swarming Rat", fight=2, health=1, damage=1, horror=1,
    ))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=2)
    g.card_registry.register_class(ManoAMano)

    inv = g.state.get_investigator("inv1")
    inv.hand.append("mano_a_mano_lv1")
    inv.actions_remaining = 3
    return g


def _spawn_engaged(game, instance_id="enemy_1"):
    enemy = CardInstance(
        instance_id=instance_id, card_id="rat",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    game.state.get_investigator("inv1").threat_area.append(instance_id)
    return enemy


class TestManoAMano:
    def test_first_action_deals_1_and_can_defeat(self, game):
        """作为第一个行动打出：对交战敌人造成1点伤害（1血老鼠被击败）。"""
        _spawn_engaged(game)
        inv = game.state.get_investigator("inv1")

        ok = game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="mano_a_mano_lv1",
        )
        assert ok is True
        assert inv.actions_remaining == 2  # 消耗了1个行动
        # 敌人被击败离场
        assert "enemy_1" not in inv.threat_area
        assert game.state.get_card_instance("enemy_1") is None
        assert "rat" in game.state.scenario.encounter_discard
        # 打出行动未引起趁乱攻击（敌人已死且豁免标记生效）
        assert inv.damage == 0 and inv.horror == 0

    def test_not_first_action_fizzles(self, game):
        """非本回合第一个行动（剩余行动<3）：效果不结算。"""
        enemy = _spawn_engaged(game)
        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 2  # 已经做过一个行动

        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="mano_a_mano_lv1",
        )
        assert enemy.damage == 0
        assert "enemy_1" in inv.threat_area
