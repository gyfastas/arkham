"""Tests for Devil's Luck (Level 1)."""

import pytest
from backend.cards.survivor.devils_luck_lv1 import DevilsLuck
from backend.models.enums import PlayerClass
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="devils_luck_lv1", name="Devil's Luck", cost=1,
        card_class=PlayerClass.SURVIVOR, fast=True,
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(DevilsLuck)
    impl = DevilsLuck("impl_1")
    impl.register(g.event_bus, "impl_1")
    return g


class TestDevilsLuck:
    def test_card_registered(self, game):
        assert "devils_luck_lv1" in game.card_registry.registered_cards

    def test_cancels_damage_and_exiles(self, game):
        """被造成3伤害：自动打出全部取消，卡牌放逐（不入弃牌堆）。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["devils_luck_lv1"]
        inv.resources = 1

        game.damage_engine.deal_damage("inv1", damage=3)
        assert inv.damage == 0
        assert "devils_luck_lv1" in game.state.scenario.vars["exiled_cards"]
        assert "devils_luck_lv1" not in inv.discard
        assert "devils_luck_lv1" not in inv.hand
        assert inv.resources == 0

    def test_cancels_horror(self, game):
        inv = game.state.get_investigator("inv1")
        inv.hand = ["devils_luck_lv1"]
        inv.resources = 1

        game.damage_engine.deal_damage("inv1", horror=2)
        assert inv.horror == 0
        assert "devils_luck_lv1" in game.state.scenario.vars["exiled_cards"]

    def test_cancels_both_damage_and_horror_from_same_hit(self, game):
        """同时伤害+恐惧：两个事件各自取消（简化，见卡内注释）。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["devils_luck_lv1", "devils_luck_lv1"]  # 两张副本各管一段
        inv.resources = 2

        game.damage_engine.deal_damage("inv1", damage=1, horror=1)
        assert inv.damage == 0
        assert inv.horror == 0

    def test_no_trigger_without_resources(self, game):
        inv = game.state.get_investigator("inv1")
        inv.hand = ["devils_luck_lv1"]
        inv.resources = 0

        game.damage_engine.deal_damage("inv1", damage=2)
        assert inv.damage == 2
        assert "devils_luck_lv1" in inv.hand

    def test_no_trigger_when_not_in_hand(self, game):
        inv = game.state.get_investigator("inv1")
        inv.hand = []
        inv.resources = 5

        game.damage_engine.deal_damage("inv1", damage=2)
        assert inv.damage == 2
