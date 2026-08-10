"""Tests for Blood Will Have Blood (Level 2)."""

import pytest

from backend.cards.survivor.blood_will_have_blood_lv2 import BloodWillHaveBlood
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import GameEvent
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data(health=9, sanity=9)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="blood_will_have_blood_lv2", name="Blood Will Have Blood",
        cost=1, fast=True))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(BloodWillHaveBlood)
    impl = BloodWillHaveBlood("impl_bwhb")
    impl.register(g.event_bus, "impl_bwhb")
    return g


class TestBloodWillHaveBlood:
    def test_card_registered(self, game):
        assert "blood_will_have_blood_lv2" in game.card_registry.registered_cards

    def test_draw_per_point_taken(self, game):
        """敌人攻击造成2伤害+1恐惧：自动打出（1次），共抽3张牌。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["blood_will_have_blood_lv2"]
        inv.resources = 3
        inv.deck = ["deck_a", "deck_b", "deck_c", "deck_d"]

        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.ENEMY_ATTACKS,
            investigator_id="inv1", enemy_id="enemy_1",
        ))
        game.damage_engine.deal_damage(
            "inv1", damage=2, horror=1, source="enemy_1")

        assert inv.damage == 2
        assert inv.horror == 1
        for c in ("deck_a", "deck_b", "deck_c"):
            assert c in inv.hand
        assert "blood_will_have_blood_lv2" in inv.discard
        assert inv.resources == 2  # 只打出1次

    def test_no_trigger_without_enemy_attack(self, game):
        """非敌人攻击来源的伤害不触发。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["blood_will_have_blood_lv2"]
        inv.resources = 3
        inv.deck = ["deck_a"]
        game.damage_engine.deal_damage("inv1", damage=2, source="some_treachery")
        assert "blood_will_have_blood_lv2" in inv.hand
        assert "deck_a" in inv.deck
