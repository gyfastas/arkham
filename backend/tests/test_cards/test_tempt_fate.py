"""Tests for Tempt Fate (Level 0)."""

from backend.cards.neutral.tempt_fate_lv0 import TemptFate
from backend.engine.event_bus import EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent


def _play(game, impl):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id="test_investigator",
        extra={"card_id": "tempt_fate_lv0"},
    )
    game.event_bus.emit(ctx)
    return ctx


class TestTemptFate:
    def test_adds_tokens_and_draws(self, game):
        """+3诅咒、+3祝福入袋，抽1张牌。"""
        impl = TemptFate("tf_1")
        impl.register(game.event_bus, "tf_1")
        bag = ChaosBag(tokens=[ChaosTokenType.ZERO])
        impl.bind_chaos_bag(bag)

        inv = game.state.get_investigator("test_investigator")
        inv.deck = ["card_a"]
        hand_before = len(inv.hand)

        ctx = _play(game, impl)
        curses = [t for t in bag.tokens if t == ChaosTokenType.CURSE]
        blesses = [t for t in bag.tokens if t == ChaosTokenType.BLESS]
        assert len(curses) == 3
        assert len(blesses) == 3
        assert len(bag.tokens) == 7  # 1 + 3 + 3
        assert len(inv.hand) == hand_before + 1
        assert "card_a" in inv.hand
        assert ctx.extra["tempt_fate_resolved"] is True

    def test_without_bag_still_draws(self, game):
        """未绑定混沌袋：仅抽牌。"""
        impl = TemptFate("tf_1")
        impl.register(game.event_bus, "tf_1")
        inv = game.state.get_investigator("test_investigator")
        inv.deck = ["card_a"]
        ctx = _play(game, impl)
        assert "card_a" in inv.hand
