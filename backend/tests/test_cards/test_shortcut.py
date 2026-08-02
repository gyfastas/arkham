"""Tests for Shortcut (Level 0).

Official: Fast. Play only during your turn. Choose an investigator at your
location. Move that investigator to a connecting location.

Flow: playing the card sets pending_choice (kind="shortcut_move"); the player
picks a connecting location; the session layer performs the move.
"""

import pytest
from backend.cards.seeker.shortcut_lv0 import Shortcut
from backend.engine.event_bus import EventBus, EventContext
from backend.engine.game import Game
from backend.models.enums import GameEvent
from backend.models.state import CardInstance
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def game():
    g = Game("test_shortcut")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)

    loc_a = make_location_data(id="loc_a", name="Hallway", connections=["loc_b", "loc_c"])
    loc_b = make_location_data(id="loc_b", name="Study", connections=["loc_a"])
    loc_c = make_location_data(id="loc_c", name="Cellar", connections=["loc_a"])
    for loc in (loc_a, loc_b, loc_c):
        g.register_card_data(loc)

    g.add_investigator("player", inv_data, deck=["shortcut_lv0"] * 3,
                       starting_location="loc_a")
    g.add_location("loc_a", loc_a, clues=1)
    g.add_location("loc_b", loc_b, clues=1)
    g.add_location("loc_c", loc_c, clues=1)

    g.card_registry.register_class(Shortcut)
    return g


def _play_shortcut(game):
    """Simulate the CARD_PLAYED emit that _play_event performs."""
    impl = Shortcut("shortcut_temp")
    impl.register(game.event_bus, "shortcut_temp")
    ctx = EventContext(
        game_state=game.state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="player",
        extra={"card_id": "shortcut_lv0"},
    )
    game.event_bus.emit(ctx)
    return ctx


def _make_session(game):
    from server.game_session import GameSession
    session = GameSession.__new__(GameSession)
    session.game = game
    session.action_log = []
    session.controller = None
    session.game_over = None
    session.event_logger = None
    return session


class TestShortcut:
    def test_play_sets_pending_choice_and_does_not_move(self, game):
        inv = game.state.get_investigator("player")
        _play_shortcut(game)

        # No immediate move — the player must choose
        assert inv.location_id == "loc_a"

        pc = game.state.scenario.vars.get("pending_choice")
        assert pc is not None
        assert pc["kind"] == "shortcut_move"
        assert pc["investigator_id"] == "player"
        assert pc["from_location"] == "loc_a"
        option_ids = {o["id"] for o in pc["options"]}
        assert option_ids == {"loc_b", "loc_c"}
        labels = {o["label"] for o in pc["options"]}
        assert "测试地点" in labels or "Study" in labels  # name_cn fallback

    def test_resolve_choice_moves_investigator(self, game):
        inv = game.state.get_investigator("player")
        _play_shortcut(game)
        session = _make_session(game)

        result = session._resolve_choice({"choice_id": "loc_c"})
        assert result["success"] is True
        assert inv.location_id == "loc_c"
        assert "pending_choice" not in game.state.scenario.vars
        assert any("捷径" in line for line in session.action_log)

    def test_resolve_rejects_invalid_destination(self, game):
        inv = game.state.get_investigator("player")
        _play_shortcut(game)
        session = _make_session(game)

        result = session._resolve_choice({"choice_id": "loc_nonexistent"})
        assert result["success"] is False
        assert inv.location_id == "loc_a"

    def test_no_connections_is_noop(self, game):
        # Move investigator to loc_b which only connects back to loc_a…
        # give it an isolated location instead
        isolated = make_location_data(id="loc_iso", name="Nowhere", connections=[])
        game.register_card_data(isolated)
        game.add_location("loc_iso", isolated, clues=0)
        inv = game.state.get_investigator("player")
        inv.location_id = "loc_iso"

        _play_shortcut(game)
        assert game.state.scenario.vars.get("pending_choice") is None
        assert inv.location_id == "loc_iso"

    def test_other_card_played_does_not_trigger(self, game):
        impl = Shortcut("shortcut_temp")
        impl.register(game.event_bus, "shortcut_temp")
        ctx = EventContext(
            game_state=game.state,
            event=GameEvent.CARD_PLAYED,
            investigator_id="player",
            extra={"card_id": "some_other_card"},
        )
        game.event_bus.emit(ctx)
        assert game.state.scenario.vars.get("pending_choice") is None


class TestShortcutRealPlayFlow:
    """End-to-end through ActionResolver._play_event (temp activation)."""

    def test_play_via_action_sets_pending_choice(self, game):
        from backend.models.enums import Action
        from backend.models.state import CardData
        from backend.models.enums import CardType, PlayerClass

        # Register real shortcut card data + put in hand
        game.register_card_data(CardData(
            id="shortcut_lv0", name="Shortcut", name_cn="捷径",
            type=CardType.EVENT, card_class=PlayerClass.SEEKER, cost=0,
            traits=["insight", "tactic"], fast=True,
        ))
        game.setup()  # triggers discover_cards()
        inv = game.state.get_investigator("player")
        inv.hand = ["shortcut_lv0"]
        inv.resources = 5
        inv.actions_remaining = 3

        ok = game.action_resolver.perform_action(
            "player", Action.PLAY, card_id="shortcut_lv0"
        )
        assert ok is True
        assert "shortcut_lv0" in inv.discard
        assert inv.location_id == "loc_a"  # not moved yet

        pc = game.state.scenario.vars.get("pending_choice")
        assert pc is not None and pc["kind"] == "shortcut_move"

        # Resolve: pick loc_b
        session = _make_session(game)
        result = session._resolve_choice({"choice_id": "loc_b"})
        assert result["success"] is True
        assert inv.location_id == "loc_b"
