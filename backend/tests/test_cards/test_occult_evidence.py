"""Tests for Occult Evidence (Level 0)."""

import pytest
from backend.cards.neutral.occult_evidence_lv0 import OccultEvidence
from backend.engine.game import Game
from backend.models.enums import Action
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data())
    g.register_card_data(make_location_data())
    g.register_card_data(make_event_data(
        id="occult_evidence_lv0", name="Occult Evidence",
    ))
    g.register_card_data(make_event_data(id="guts_lv0", name="Guts"))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"),
                   clues=2)
    g.card_registry.register_class(OccultEvidence)
    inv = g.state.get_investigator("inv1")
    inv.hand.append("occult_evidence_lv0")
    inv.resources = 5
    return g


def _play(game):
    game.action_resolver.perform_action(
        "inv1", Action.PLAY, card_id="occult_evidence_lv0",
    )
    return next(
        i for i in game.card_registry.active_instances.values()
        if isinstance(i, OccultEvidence)
    )


class TestOccultEvidence:
    def test_play_shuffles_into_deck(self, game):
        """打出：洗入牌组。"""
        _play(game)
        inv = game.state.get_investigator("inv1")
        assert "occult_evidence_lv0" in inv.deck

    def test_reaction_on_search_draws_and_discovers_clue(self, game):
        """检索牌库时展示：抽取并在所在地点发现1条线索。"""
        impl = _play(game)
        inv = game.state.get_investigator("inv1")
        assert impl.on_deck_searched(game.state, "inv1") is True
        assert "occult_evidence_lv0" in inv.hand
        assert "occult_evidence_lv0" not in inv.deck
        assert inv.clues == 1
        assert game.state.get_location("test_location").clues == 1

    def test_no_trigger_when_not_searched(self, game):
        """不在被检索卡牌中：不触发。"""
        impl = _play(game)
        inv = game.state.get_investigator("inv1")
        assert impl.on_deck_searched(
            game.state, "inv1", searched_card_ids=["guts_lv0"],
        ) is False
        assert "occult_evidence_lv0" in inv.deck
        assert inv.clues == 0
