"""Tests for Stirring Up Trouble (Level 1).

官方：作为打出的额外费用，加入数量等于你所在地点隐藏值的[curse]标记
到混乱袋。发现你所在地点的2个线索。
"""

import pytest

from backend.cards.seeker.stirring_up_trouble_lv1 import StirringUpTrouble
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent
from backend.tests.conftest import (
    make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_stirring_up_trouble")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a", shroud=3)
    g.register_card_data(loc_data)
    g.add_investigator("player", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_data, clues=3)

    g.card_registry.register_class(StirringUpTrouble)
    g.card_registry.activate_card(
        "stirring_up_trouble_lv1", "impl_sut", g.event_bus,
        chaos_bag=g.chaos_bag)
    return g


def _play(game):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id="player",
        extra={"card_id": "stirring_up_trouble_lv1"},
    )
    game.event_bus.emit(ctx)
    return ctx


class TestStirringUpTrouble:
    def test_adds_curses_and_discovers_two_clues(self, game):
        """加入隐藏值(3)个诅咒标记；发现2个线索。"""
        inv = game.state.get_investigator("player")
        loc = game.state.get_location("loc_a")
        tokens_before = len(game.chaos_bag.tokens)
        ctx = _play(game)
        curses = sum(1 for t in game.chaos_bag.tokens
                     if t == ChaosTokenType.CURSE)
        assert curses == 3
        assert len(game.chaos_bag.tokens) == tokens_before + 3
        assert ctx.extra.get("stirring_up_trouble_curses") == 3
        assert ctx.extra.get("stirring_up_trouble_clues") == 2
        assert inv.clues == 2
        assert loc.clues == 1

    def test_fewer_clues_discovers_what_is_there(self, game):
        """地点只有1个线索时发现1个；诅咒仍全额加入。"""
        inv = game.state.get_investigator("player")
        loc = game.state.get_location("loc_a")
        loc.clues = 1
        ctx = _play(game)
        assert ctx.extra.get("stirring_up_trouble_clues") == 1
        assert inv.clues == 1
        curses = sum(1 for t in game.chaos_bag.tokens
                     if t == ChaosTokenType.CURSE)
        assert curses == 3
