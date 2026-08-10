"""Tests for Heroic Rescue (Level 0). (03106)

快速。非精英敌人将要攻击你所在地点的另一位调查员时打出：
改为与它交战并结算它对你的攻击，然后对其造成1点伤害。
"""

import pytest
from backend.cards.guardian.heroic_rescue_lv0 import HeroicRescue
from backend.engine.game import Game
from backend.models.enums import PlayerClass
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)
from backend.models.state import CardInstance


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    inv_data2 = make_investigator_data(id="inv2_card", name="Second")
    g.register_card_data(inv_data2)
    g.register_card_data(make_location_data())
    g.register_card_data(make_event_data(
        id="heroic_rescue_lv0", name="Heroic Rescue", cost=1, fast=True,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(make_enemy_data(
        id="ghoul", name="Ghoul", fight=3, health=3, damage=1, horror=1,
    ))
    g.register_card_data(make_enemy_data(
        id="elite_cultist", name="Elite Cultist", fight=3, health=3,
        damage=2, horror=0, keywords=["elite"],
    ))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_investigator("inv2", inv_data2, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=2)
    g.card_registry.register_class(HeroicRescue)

    inv1 = g.state.get_investigator("inv1")
    inv1.hand.append("heroic_rescue_lv0")
    inv1.resources = 3
    g.card_registry.activate_card("heroic_rescue_lv0", "hr_1", g.event_bus)
    return g


def _spawn_engaged(game, card_id, target_inv, instance_id="enemy_1"):
    enemy = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    game.state.get_investigator(target_inv).threat_area.append(instance_id)
    return enemy


class TestHeroicRescue:
    def test_intercepts_attack_on_other_investigator(self, game):
        """敌人攻击同地点另一位调查员：改为攻击持有者，敌人反受1点。"""
        enemy = _spawn_engaged(game, "ghoul", "inv2")
        inv1 = game.state.get_investigator("inv1")
        inv2 = game.state.get_investigator("inv2")

        game.enemy_phase.resolve()

        # 持有者承受攻击（1伤害1恐惧），另一位不受伤害
        assert inv1.damage == 1 and inv1.horror == 1
        assert inv2.damage == 0 and inv2.horror == 0
        # 与持有者交战 + 反打1点
        assert "enemy_1" in inv1.threat_area
        assert "enemy_1" not in inv2.threat_area
        assert enemy.damage == 1
        # 从手牌打出并付费
        assert "heroic_rescue_lv0" in inv1.discard
        assert inv1.resources == 2

    def test_no_intercept_for_elite(self, game):
        """精英敌人的攻击不触发。"""
        _spawn_engaged(game, "elite_cultist", "inv2")
        inv1 = game.state.get_investigator("inv1")
        inv2 = game.state.get_investigator("inv2")

        game.enemy_phase.resolve()

        assert inv2.damage == 2  # 原目标正常承受攻击
        assert inv1.damage == 0
        assert "heroic_rescue_lv0" in inv1.hand  # 未打出

    def test_no_intercept_for_own_attacker(self, game):
        """攻击持有者自己的敌人不触发。"""
        _spawn_engaged(game, "ghoul", "inv1")
        inv1 = game.state.get_investigator("inv1")

        game.enemy_phase.resolve()

        assert inv1.damage == 1  # 正常承受
        assert "heroic_rescue_lv0" in inv1.hand
