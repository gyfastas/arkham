"""Tests for Fortune or Fate (Level 2)."""

import pytest

from backend.cards.survivor.fortune_or_fate_lv2 import FortuneOrFate
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import GameEvent
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="fortune_or_fate_lv2", name="Fortune or Fate", cost=2, fast=True))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(FortuneOrFate)
    impl = FortuneOrFate("impl_fof")
    impl.register(g.event_bus, "impl_fof")
    return g


def _place_doom(game):
    game.state.scenario.doom_on_agenda += 1
    game.event_bus.emit(EventContext(
        game_state=game.state, event=GameEvent.DOOM_PLACED, amount=1))


class TestFortuneOrFate:
    def test_card_registered(self, game):
        assert "fortune_or_fate_lv2" in game.card_registry.registered_cards

    def test_cancels_doom_and_exiles(self, game):
        """毁灭放置时自动打出：取消1毁灭，放逐本卡。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["fortune_or_fate_lv2"]
        inv.resources = 5

        _place_doom(game)
        assert game.state.scenario.doom_on_agenda == 0
        assert inv.resources == 3
        assert "fortune_or_fate_lv2" not in inv.hand
        assert "fortune_or_fate_lv2" in \
            game.state.scenario.vars["exiled_cards"]
        assert game.state.scenario.vars["fortune_or_fate_used"] is True

    def test_max_once_per_game(self, game):
        """每场游戏最多1次：第二次放置毁灭不再触发。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["fortune_or_fate_lv2"]
        inv.resources = 5

        _place_doom(game)
        # 模拟第二张（另一份副本在手）
        inv.hand = ["fortune_or_fate_lv2"]
        _place_doom(game)
        assert game.state.scenario.doom_on_agenda == 1
        assert "fortune_or_fate_lv2" in inv.hand
