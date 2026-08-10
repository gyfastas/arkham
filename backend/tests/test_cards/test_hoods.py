"""Tests for Hoods (Level 0 enemy weakness)."""

import pytest
from backend.cards.neutral.hoods_lv0 import Hoods
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data(agility=5))
    g.register_card_data(make_location_data())
    g.register_card_data(make_enemy_data(
        id="hoods_lv0", name="Hoods", fight=3, health=3, evade=2,
        damage=2, horror=1, keywords=["alert", "hunter"],
    ))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(Hoods)
    # 固定袋中只有 0：5敏捷 vs 2躲避 必成功
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]

    enemy = CardInstance(
        instance_id="hoods_1", card_id="hoods_lv0",
        owner_id="inv1", controller_id="scenario",
    )
    g.state.cards_in_play["hoods_1"] = enemy
    g.state.get_investigator("inv1").threat_area.append("hoods_1")
    g.card_registry.activate_card("hoods_lv0", "hoods_1", g.event_bus,
                                  chaos_bag=g.chaos_bag)
    return g


class TestHoods:
    def test_attacks_after_being_evaded(self, game):
        """强制 - 躲避暴徒后：它攻击你（2伤害1恐惧）。"""
        inv = game.state.get_investigator("inv1")
        ok = game.action_resolver.perform_action(
            "inv1", Action.EVADE, enemy_instance_id="hoods_1",
        )
        assert ok is True
        assert "hoods_1" not in inv.threat_area  # 已脱离交战
        assert inv.damage == 2
        assert inv.horror == 1
