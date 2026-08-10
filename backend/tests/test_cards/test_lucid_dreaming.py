"""Tests for Lucid Dreaming (Level 2)."""

import pytest
from backend.cards.neutral.lucid_dreaming_lv2 import LucidDreaming
from backend.engine.game import Game
from backend.models.enums import Action
from backend.tests.conftest import (
    make_asset_data, make_event_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data())
    g.register_card_data(make_location_data())
    g.register_card_data(make_event_data(
        id="lucid_dreaming_lv2", name="Lucid Dreaming", cost=1,
    ))
    g.register_card_data(make_asset_data(id="machete_lv0", name="Machete"))
    g.register_card_data(make_event_data(id="guts_lv0", name="Guts"))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(LucidDreaming)
    inv = g.state.get_investigator("inv1")
    inv.resources = 5
    return g


class TestLucidDreaming:
    def test_search_deck_for_copy(self, game):
        """打出后默认以手牌首张为目标：从牌库抽其复制并洗牌。"""
        inv = game.state.get_investigator("inv1")
        inv.hand.extend(["lucid_dreaming_lv2", "machete_lv0"])
        inv.deck = ["guts_lv0", "machete_lv0"]
        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="lucid_dreaming_lv2",
        )
        assert inv.hand.count("machete_lv0") == 2
        assert "machete_lv0" not in inv.deck
        assert inv.deck == ["guts_lv0"]  # 洗牌后仅余1张

    def test_no_copy_in_deck(self, game):
        """牌库无复制：手牌不变。"""
        inv = game.state.get_investigator("inv1")
        inv.hand.extend(["lucid_dreaming_lv2", "machete_lv0"])
        inv.deck = ["guts_lv0"]
        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="lucid_dreaming_lv2",
        )
        assert inv.hand.count("machete_lv0") == 1
