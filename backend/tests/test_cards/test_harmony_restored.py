"""Tests for Harmony Restored (Level 2) and Keep Faith (Level 0)."""

import pytest
from backend.cards.survivor.harmony_restored_lv2 import HarmonyRestored
from backend.cards.survivor.keep_faith_lv0 import KeepFaith
from backend.models.enums import Action, ChaosTokenType, PlayerClass
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="harmony_restored_lv2", name="Harmony Restored", cost=3,
        card_class=PlayerClass.SURVIVOR))
    g.register_card_data(make_event_data(
        id="keep_faith_lv0", name="Keep Faith", cost=2,
        card_class=PlayerClass.SURVIVOR, fast=True))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(HarmonyRestored)
    g.card_registry.register_class(KeepFaith)
    return g


def _count(game, token):
    return sum(1 for t in game.chaos_bag.tokens if t == token)


class TestHarmonyRestored:
    def test_card_registered(self, game):
        assert "harmony_restored_lv2" in game.card_registry.registered_cards

    def test_remove_curses_up_to_bless_count(self, game):
        """X=袋中祝福数：移除至多X个诅咒，每移除1个得1资源。"""
        game.chaos_bag.tokens = [
            ChaosTokenType.BLESS, ChaosTokenType.BLESS,
            ChaosTokenType.CURSE, ChaosTokenType.CURSE, ChaosTokenType.CURSE,
            ChaosTokenType.ZERO,
        ]
        inv = game.state.get_investigator("inv1")
        inv.hand = ["harmony_restored_lv2"]
        inv.resources = 5

        assert game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="harmony_restored_lv2") is True

        # 2祝福 → 移除2诅咒（剩1），+2资源；净资源 5-3+2=4
        assert _count(game, ChaosTokenType.CURSE) == 1
        assert _count(game, ChaosTokenType.BLESS) == 2
        assert inv.resources == 4

    def test_no_curses_no_resources(self, game):
        game.chaos_bag.tokens = [ChaosTokenType.BLESS, ChaosTokenType.ZERO]
        inv = game.state.get_investigator("inv1")
        inv.hand = ["harmony_restored_lv2"]
        inv.resources = 5

        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="harmony_restored_lv2")

        assert inv.resources == 2  # 仅支付3费，无诅咒可移除


class TestKeepFaith:
    def test_card_registered(self, game):
        assert "keep_faith_lv0" in game.card_registry.registered_cards

    def test_adds_four_bless_tokens(self, game):
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = game.state.get_investigator("inv1")
        inv.hand = ["keep_faith_lv0"]

        assert game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="keep_faith_lv0") is True

        assert _count(game, ChaosTokenType.BLESS) == 4
        assert _count(game, ChaosTokenType.ZERO) == 1
