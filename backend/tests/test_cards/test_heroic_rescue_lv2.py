"""Tests for Heroic Rescue (Level 2). (06234)

快速。非精英敌人将要攻击你所在地点或连接地点的另一位调查员时打出：
移动过去，与之交战并代为承受攻击，然后对其造成1点伤害。
"""

import pytest
from backend.cards.guardian.heroic_rescue_lv2 import HeroicRescueLv2
from backend.engine.game import Game
from backend.models.enums import PlayerClass
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
    inv_data2 = make_investigator_data(id="inv2_card", name="Second")
    g.register_card_data(inv_data2)
    loc_a = make_location_data(id="loc_a", name="A", connections=["loc_b"])
    loc_b = make_location_data(id="loc_b", name="B", connections=["loc_a"])
    g.register_card_data(loc_a)
    g.register_card_data(loc_b)
    g.register_card_data(make_event_data(
        id="heroic_rescue_lv2", name="Heroic Rescue", cost=0, fast=True,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(make_enemy_data(
        id="ghoul", name="Ghoul", fight=3, health=3, damage=1, horror=1))
    g.register_card_data(make_enemy_data(
        id="elite_cultist", name="Elite", fight=3, health=3,
        damage=2, horror=0, keywords=["elite"]))

    g.add_investigator("inv1", inv_data, starting_location="loc_a")
    g.add_investigator("inv2", inv_data2, starting_location="loc_b")
    g.add_location("loc_a", loc_a, clues=0)
    g.add_location("loc_b", loc_b, clues=0)
    g.card_registry.register_class(HeroicRescueLv2)

    inv1 = g.state.get_investigator("inv1")
    inv1.hand.append("heroic_rescue_lv2")
    g.card_registry.activate_card("heroic_rescue_lv2", "hr_1", g.event_bus)
    return g


def _spawn_engaged(game, card_id, target_inv, instance_id="enemy_1"):
    enemy = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    game.state.get_investigator(target_inv).threat_area.append(instance_id)
    return enemy


class TestHeroicRescueLv2:
    def test_intercepts_at_connecting_location(self, game):
        """连接地点的另一调查员被攻击：持有者移动过去代为承受并反打1点。"""
        enemy = _spawn_engaged(game, "ghoul", "inv2")
        inv1 = game.state.get_investigator("inv1")
        inv2 = game.state.get_investigator("inv2")

        game.enemy_phase.resolve()

        # 持有者移动到连接地点并承受攻击
        assert inv1.location_id == "loc_b"
        assert inv1.damage == 1 and inv1.horror == 1
        assert inv2.damage == 0 and inv2.horror == 0
        # 交战转移 + 反打1点
        assert "enemy_1" in inv1.threat_area
        assert "enemy_1" not in inv2.threat_area
        assert enemy.damage == 1
        assert "heroic_rescue_lv2" in inv1.discard

    def test_no_intercept_for_elite(self, game):
        """精英敌人的攻击不触发。"""
        _spawn_engaged(game, "elite_cultist", "inv2")
        inv1 = game.state.get_investigator("inv1")
        inv2 = game.state.get_investigator("inv2")

        game.enemy_phase.resolve()

        assert inv2.damage == 2
        assert inv1.damage == 0
        assert inv1.location_id == "loc_a"
        assert "heroic_rescue_lv2" in inv1.hand

    def test_intercepts_same_location(self, game):
        """同地点（lv0 原有能力）仍然生效，且不移动。"""
        inv2 = game.state.get_investigator("inv2")
        inv2.location_id = "loc_a"
        enemy = _spawn_engaged(game, "ghoul", "inv2")
        inv1 = game.state.get_investigator("inv1")

        game.enemy_phase.resolve()

        assert inv1.location_id == "loc_a"  # 无需移动
        assert inv1.damage == 1
        assert enemy.damage == 1
