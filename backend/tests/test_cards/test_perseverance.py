"""Tests for Perseverance (Level 0)."""

import pytest
from backend.cards.survivor.perseverance_lv0 import Perseverance
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(health=7, sanity=7)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="perseverance_lv0", name="Perseverance", cost=2))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(Perseverance)
    impl = Perseverance("impl_perseverance")
    impl.register(g.event_bus, "impl_perseverance")
    return g


class TestPerseverance:
    def test_card_registered(self, game):
        assert "perseverance_lv0" in game.card_registry.registered_cards

    def test_cancels_up_to_4_when_would_defeat(self, game):
        """分配将导致被击败的伤害时：自动打出并取消至多4点。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["perseverance_lv0"]
        inv.damage = 5  # 生命7：再受2点即被击败
        inv.resources = 3

        game.damage_engine.deal_damage("inv1", damage=5)

        assert inv.damage == 5 + 1  # 取消4点，仅承受1点
        assert "perseverance_lv0" in inv.discard
        assert inv.resources == 1

    def test_cancels_horror_when_would_defeat(self, game):
        inv = game.state.get_investigator("inv1")
        inv.hand = ["perseverance_lv0"]
        inv.horror = 6  # 理智7
        inv.resources = 2

        game.damage_engine.deal_damage("inv1", horror=3)

        assert inv.horror == 6  # 3点全部取消
        assert "perseverance_lv0" in inv.discard

    def test_no_trigger_when_not_lethal(self, game):
        """不足以致败的伤害不触发。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["perseverance_lv0"]
        inv.resources = 5

        game.damage_engine.deal_damage("inv1", damage=2)

        assert inv.damage == 2
        assert "perseverance_lv0" in inv.hand  # 未打出

    def test_no_trigger_without_resources(self, game):
        inv = game.state.get_investigator("inv1")
        inv.hand = ["perseverance_lv0"]
        inv.damage = 6
        inv.resources = 1  # 付不起2费

        game.damage_engine.deal_damage("inv1", damage=2)

        assert inv.damage == 8  # 未取消（已致败）
        assert "perseverance_lv0" in inv.hand
