"""Tests for The Harbinger (Level 0)."""

from backend.cards.neutral.the_harbinger_lv0 import TheHarbinger
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent


def _draw(game):
    impl = TheHarbinger("harb_1")
    impl.register(game.event_bus, "harb_1")
    inv = game.state.get_investigator("test_investigator")
    inv.hand.append("the_harbinger_lv0")
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_DRAWN,
        investigator_id="test_investigator",
        extra={"card_id": "the_harbinger_lv0"},
    )
    game.event_bus.emit(ctx)
    return impl, ctx


class TestTheHarbinger:
    def test_revelation_places_on_deck_top(self, game):
        """显现：放置在牌堆顶。"""
        inv = game.state.get_investigator("test_investigator")
        inv.deck = ["card_a", "card_b"]
        impl, ctx = _draw(game)
        assert ctx.extra["the_harbinger_on_deck"] is True
        assert inv.deck[0] == "the_harbinger_lv0"
        assert "the_harbinger_lv0" not in inv.hand
        assert len(inv.deck) == 3

    def test_deck_locked_while_on_top(self, game):
        """在牌堆顶时：牌组不能被检索/抽取/操纵。"""
        _draw(game)
        impl = TheHarbinger("harb_2")
        # 查询方法只读 game_state，与注册实例无关
        inv = game.state.get_investigator("test_investigator")
        assert inv.deck[0] == "the_harbinger_lv0"
        assert impl.can_draw_or_search_deck(game.state, "test_investigator") is False

    def test_discard_from_deck_top(self, game):
        """[行动×2]：从牌堆顶丢弃先兆，牌组解锁。"""
        impl, _ = _draw(game)
        inv = game.state.get_investigator("test_investigator")
        assert impl.activate_discard(game.state, "test_investigator") is True
        assert "the_harbinger_lv0" in inv.discard
        assert not (inv.deck and inv.deck[0] == "the_harbinger_lv0")
        assert impl.can_draw_or_search_deck(game.state, "test_investigator") is True
