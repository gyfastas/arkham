"""Tests for "Get behind me!" (Level 0). (08021)

快速。直到本阶段结束，敌人将要攻击你所在地点另一位调查员时改为攻击你
并与你交战；每次这样的攻击取消1点恐惧。
"""

import pytest
from backend.cards.guardian.get_behind_me_lv0 import GetBehindMe
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
    g.register_card_data(make_location_data())
    g.register_card_data(make_event_data(
        id="get_behind_me_lv0", name="Get behind me!", cost=0, fast=True,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(make_enemy_data(
        id="ghoul", name="Ghoul", fight=3, health=3, damage=1, horror=2))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_investigator("inv2", inv_data2, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=0)
    g.card_registry.register_class(GetBehindMe)

    inv1 = g.state.get_investigator("inv1")
    inv1.hand.append("get_behind_me_lv0")
    g.card_registry.activate_card("get_behind_me_lv0", "gbm_1", g.event_bus)
    return g


def _spawn_engaged(game, card_id, target_inv, instance_id):
    game.state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    game.state.get_investigator(target_inv).threat_area.append(instance_id)
    return game.state.cards_in_play[instance_id]


class TestGetBehindMe:
    def test_redirects_attack_and_cancels_1_horror(self, game):
        """敌人攻击同地点另一调查员：改为攻击持有者，恐惧-1。"""
        _spawn_engaged(game, "ghoul", "inv2", "enemy_1")
        inv1 = game.state.get_investigator("inv1")
        inv2 = game.state.get_investigator("inv2")

        game.enemy_phase.resolve()

        # 持有者承受攻击：1伤害 + (2-1)=1恐惧
        assert inv1.damage == 1
        assert inv1.horror == 1
        assert inv2.damage == 0 and inv2.horror == 0
        # 敌人改与持有者交战
        assert "enemy_1" in inv1.threat_area
        assert "enemy_1" not in inv2.threat_area
        # 已打出
        assert "get_behind_me_lv0" in inv1.discard
        assert "get_behind_me_lv0" not in inv1.hand

    def test_persists_until_phase_end(self, game):
        """打出后本阶段内后续攻击同样转移。"""
        _spawn_engaged(game, "ghoul", "inv2", "enemy_1")
        _spawn_engaged(game, "ghoul", "inv2", "enemy_2")
        inv1 = game.state.get_investigator("inv1")
        inv2 = game.state.get_investigator("inv2")

        game.enemy_phase.resolve()

        assert inv1.damage == 2 and inv1.horror == 2
        assert inv2.damage == 0
        assert "enemy_1" in inv1.threat_area and "enemy_2" in inv1.threat_area

    def test_no_trigger_for_own_attacker(self, game):
        """攻击持有者本人的敌人不触发。"""
        _spawn_engaged(game, "ghoul", "inv1", "enemy_1")
        inv1 = game.state.get_investigator("inv1")

        game.enemy_phase.resolve()

        assert inv1.damage == 1 and inv1.horror == 2  # 正常承受
        assert "get_behind_me_lv0" in inv1.hand
