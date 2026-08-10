"""Tests for Seeking Answers (Level 0)."""

import pytest
from backend.cards.seeker.seeking_answers_lv0 import SeekingAnswers
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def game():
    g = Game("test_seeking")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(intellect=5)
    g.register_card_data(inv_data)

    loc_a = make_location_data(id="loc_a", name="Hallway", shroud=3, connections=["loc_b", "loc_c"])
    loc_b = make_location_data(id="loc_b", name="Study", shroud=2, connections=["loc_a"])
    loc_c = make_location_data(id="loc_c", name="Cellar", shroud=2, connections=["loc_a"])
    for loc in (loc_a, loc_b, loc_c):
        g.register_card_data(loc)

    g.add_investigator("inv1", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_a, clues=2)
    g.add_location("loc_b", loc_b, clues=1)
    g.add_location("loc_c", loc_c, clues=1)

    impl = SeekingAnswers("sa_1")
    impl.register(g.event_bus, "sa_1")
    return g


def _play_and_investigate(game):
    from backend.engine.event_bus import EventContext
    from backend.models.enums import GameEvent
    game.event_bus.emit(EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "seeking_answers_lv0"},
    ))
    inv = game.state.get_investigator("inv1")
    inv.actions_remaining = 3
    game.action_resolver.perform_action("inv1", Action.INVESTIGATE)


class TestSeekingAnswers:
    def test_success_discovers_at_connecting_location(self, game):
        """成功：不在本地点发现，改在第一个有线索的连接地点发现1条。"""
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = game.state.get_investigator("inv1")
        loc_a = game.state.get_location("loc_a")
        loc_b = game.state.get_location("loc_b")

        _play_and_investigate(game)

        assert inv.clues == 1
        assert loc_a.clues == 2  # 本地点线索未动
        assert loc_b.clues == 0  # 连接地点发现1条

    def test_success_with_empty_own_location(self, game):
        """本地点没有线索：成功仍可在连接地点发现1条。"""
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        loc_a = game.state.get_location("loc_a")
        loc_a.clues = 0
        loc_b = game.state.get_location("loc_b")
        inv = game.state.get_investigator("inv1")

        _play_and_investigate(game)

        assert inv.clues == 1
        assert loc_b.clues == 0

    def test_failure_no_clues(self, game):
        """失败：任何地点都不发现线索。"""
        game.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]
        inv = game.state.get_investigator("inv1")
        loc_b = game.state.get_location("loc_b")

        _play_and_investigate(game)

        assert inv.clues == 0
        assert loc_b.clues == 1

    def test_no_connecting_clues_keeps_base_discovery(self, game):
        """所有连接地点都没有线索：保留本地点的基础发现。"""
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        game.state.get_location("loc_b").clues = 0
        game.state.get_location("loc_c").clues = 0
        inv = game.state.get_investigator("inv1")
        loc_a = game.state.get_location("loc_a")

        _play_and_investigate(game)

        assert inv.clues == 1
        assert loc_a.clues == 1  # 本地点基础发现保留
