"""Tests for Shortcut (Level 2).

官方：快速。只能在你回合中打出。附加到你所在地点。被附加地点获得：
"[快速]横置捷径：移动（至1个连接地点）。本地点任意调查员可触发。"
"""

import pytest

from backend.cards.seeker.shortcut_lv2 import ShortcutLv2
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import GameEvent
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_shortcut_lv2")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc_a = make_location_data(id="loc_a", connections=["loc_b"])
    loc_b = make_location_data(id="loc_b", connections=["loc_a"])
    for loc in (loc_a, loc_b):
        g.register_card_data(loc)
    g.add_investigator("player", inv_data, deck=["shortcut_lv2"] * 2,
                       starting_location="loc_a")
    g.add_location("loc_a", loc_a, clues=1)
    g.add_location("loc_b", loc_b, clues=1)

    g.register_card_data(make_event_data(id="shortcut_lv2", cost=1, fast=True))
    g.card_registry.register_class(ShortcutLv2)
    return g


def _play(game):
    impl = ShortcutLv2("sc2_temp")
    impl.register(game.event_bus, "sc2_temp")
    ctx = EventContext(
        game_state=game.state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="player",
        extra={"card_id": "shortcut_lv2"},
    )
    game.event_bus.emit(ctx)
    return impl, ctx


def _make_session(game):
    from server.game_session import GameSession
    session = GameSession.__new__(GameSession)
    session.game = game
    session.action_log = []
    session.controller = None
    session.game_over = None
    session.event_logger = None
    return session


class TestShortcutLv2:
    def test_play_attaches_to_location(self, game):
        _, ctx = _play(game)
        assert ctx.extra["shortcut_lv2_attached"] == "loc_a"
        attached = game.state.scenario.vars["shortcut_lv2_attached"]
        assert attached["loc_a"] == {"exhausted": False}

    def test_activate_offers_move_choice(self, game):
        """本地点调查员横置捷径：产生移动选择（沿用 shortcut_move 流程）。"""
        impl, _ = _play(game)
        assert impl.activate(game.state, "player") is True

        pc = game.state.scenario.vars.get("pending_choice")
        assert pc is not None
        assert pc["kind"] == "shortcut_move"
        assert pc["from_location"] == "loc_a"
        assert {o["id"] for o in pc["options"]} == {"loc_b"}

        attached = game.state.scenario.vars["shortcut_lv2_attached"]
        assert attached["loc_a"]["exhausted"] is True

    def test_resolve_choice_moves_investigator(self, game):
        impl, _ = _play(game)
        impl.activate(game.state, "player")
        session = _make_session(game)
        result = session._resolve_choice({"choice_id": "loc_b"})
        assert result["success"] is True
        inv = game.state.get_investigator("player")
        assert inv.location_id == "loc_b"

    def test_exhausted_cannot_activate_twice(self, game):
        impl, _ = _play(game)
        assert impl.activate(game.state, "player") is True
        game.state.scenario.vars.pop("pending_choice", None)
        assert impl.activate(game.state, "player") is False

    def test_upkeep_readies_shortcut(self, game):
        """upkeep 重置横置，可再次使用。"""
        impl, _ = _play(game)
        impl.activate(game.state, "player")
        game.state.scenario.vars.pop("pending_choice", None)
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.UPKEEP_PHASE_ENDS))
        assert impl.activate(game.state, "player") is True

    def test_other_location_cannot_activate(self, game):
        """不在被附加地点的调查员无法触发。"""
        impl, _ = _play(game)
        inv = game.state.get_investigator("player")
        inv.location_id = "loc_b"
        assert impl.activate(game.state, "player") is False
