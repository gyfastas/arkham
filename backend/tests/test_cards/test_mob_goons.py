"""Tests for Mob Goons (Level 0 enemy weakness)."""

import pytest
from backend.cards.neutral.mob_goons_lv0 import MobGoons
from backend.engine.game import Game
from backend.models.enums import Phase
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data())
    g.register_card_data(make_location_data())
    g.register_card_data(make_enemy_data(
        id="mob_goons_lv0", name="Mob Goons", fight=3, health=3, evade=3,
        damage=2, horror=1, keywords=["hunter"],
    ))
    g.register_card_data(make_asset_data(
        id="leather_coat", name="Leather Coat", health=2,
    ))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(MobGoons)

    # 承伤资产：验证"视为直接"（不分配给支援卡）
    coat = CardInstance(
        instance_id="coat_1", card_id="leather_coat",
        owner_id="inv1", controller_id="inv1",
    )
    g.state.cards_in_play["coat_1"] = coat
    inv = g.state.get_investigator("inv1")
    inv.play_area.append("coat_1")

    enemy = CardInstance(
        instance_id="goons_1", card_id="mob_goons_lv0",
        owner_id="inv1", controller_id="scenario",
    )
    g.state.cards_in_play["goons_1"] = enemy
    inv.threat_area.append("goons_1")
    g.card_registry.activate_card("mob_goons_lv0", "goons_1", g.event_bus,
                                  chaos_bag=g.chaos_bag)
    return g


class TestMobGoons:
    def test_attack_is_direct_and_bypasses_soak(self, game):
        """敌方阶段攻击：伤害/恐惧视为直接（皮衣不承担）。"""
        game.state.scenario.round_number = 2
        game.enemy_phase.resolve()
        inv = game.state.get_investigator("inv1")
        assert inv.damage == 2
        assert inv.horror == 1
        coat = game.state.get_card_instance("coat_1")
        assert coat.damage == 0
