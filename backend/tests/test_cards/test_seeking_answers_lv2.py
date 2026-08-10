"""Tests for Seeking Answers (Level 2)."""

import pytest
from backend.cards.seeker.seeking_answers_lv2 import SeekingAnswersLv2
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, GameEvent
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def game():
    g = Game("test_seeking2")
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
    g.add_location("loc_b", loc_b, clues=2)
    g.add_location("loc_c", loc_c, clues=0)

    impl = SeekingAnswersLv2("sa2_1")
    impl.register(g.event_bus, "sa2_1")
    return g


def _play_and_investigate(game):
    game.event_bus.emit(EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "seeking_answers_lv2"},
    ))
    inv = game.state.get_investigator("inv1")
    inv.actions_remaining = 3
    game.action_resolver.perform_action("inv1", Action.INVESTIGATE)


class TestSeekingAnswersLv2:
    def test_success_discovers_two_total(self, game):
        """成功：本地点基础发现1条 + 第2条优先来自连接地点，共2条。"""
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = game.state.get_investigator("inv1")
        loc_a = game.state.get_location("loc_a")
        loc_b = game.state.get_location("loc_b")

        _play_and_investigate(game)

        assert inv.clues == 2
        assert loc_a.clues == 1  # 基础发现1条
        assert loc_b.clues == 1  # 连接地点补第2条

    def test_success_empty_own_location_takes_two_from_connecting(self, game):
        """本地点没有线索：成功时从连接地点共取2条。"""
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        game.state.get_location("loc_a").clues = 0
        inv = game.state.get_investigator("inv1")
        loc_b = game.state.get_location("loc_b")

        _play_and_investigate(game)

        assert inv.clues == 2
        assert loc_b.clues == 0

    def test_failure_no_clues(self, game):
        """失败：不发现任何线索。"""
        game.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]
        inv = game.state.get_investigator("inv1")

        _play_and_investigate(game)

        assert inv.clues == 0
        assert game.state.get_location("loc_a").clues == 2
        assert game.state.get_location("loc_b").clues == 2

    def test_no_auto_play_from_hand(self, game):
        """不再从手牌自动打出：普通调查成功不触发本卡效果。"""
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inv = game.state.get_investigator("inv1")
        inv.hand.append("seeking_answers_lv2")
        inv.actions_remaining = 3

        # 不打出本卡，直接调查（智力5 vs 隐蔽3，超2点）
        game.action_resolver.perform_action("inv1", Action.INVESTIGATE)

        assert inv.clues == 1  # 只有基础发现
        assert "seeking_answers_lv2" in inv.hand  # 仍在手牌
