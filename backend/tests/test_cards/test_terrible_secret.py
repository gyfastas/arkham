"""Tests for Terrible Secret (Level 0) — Diana Stanley weakness."""

from backend.cards.neutral.terrible_secret_lv0 import TerribleSecret, beneath_key
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent


def _draw(game, choices=None):
    impl = TerribleSecret("ts_1")
    impl.register(game.event_bus, "ts_1")
    inv = game.state.get_investigator("test_investigator")
    inv.hand.append("terrible_secret_lv0")
    extra = {"card_id": "terrible_secret_lv0"}
    if choices is not None:
        extra["choices"] = choices
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_DRAWN,
        investigator_id="test_investigator", extra=extra,
    )
    game.event_bus.emit(ctx)
    return ctx


class TestTerribleSecret:
    def test_horror_per_card_beneath_diana(self, game):
        """戴安娜下每张卡：默认受1恐惧。"""
        game.state.scenario.vars[beneath_key("test_investigator")] = ["c1", "c2", "c3"]
        inv = game.state.get_investigator("test_investigator")

        ctx = _draw(game)
        assert inv.horror == 3
        assert "terrible_secret_lv0" in inv.discard
        assert "terrible_secret_lv0" not in inv.hand
        # 未选择丢弃：卡牌保留在戴安娜下
        assert game.state.scenario.vars[beneath_key("test_investigator")] == ["c1", "c2", "c3"]

    def test_shuffle_back_when_nothing_beneath(self, game):
        """戴安娜下无卡：洗回牌组。"""
        inv = game.state.get_investigator("test_investigator")
        inv.deck = ["x"]

        ctx = _draw(game)
        assert ctx.extra["terrible_secret_shuffled"] is True
        assert "terrible_secret_lv0" in inv.deck
        assert inv.horror == 0

    def test_explicit_discard_choices(self, game):
        """会话层传入选择：可改为丢弃戴安娜下的卡。"""
        game.state.scenario.vars[beneath_key("test_investigator")] = ["c1", "c2"]
        inv = game.state.get_investigator("test_investigator")

        ctx = _draw(game, choices=["discard", "horror"])
        assert inv.horror == 1
        assert "c1" in inv.discard
        assert game.state.scenario.vars[beneath_key("test_investigator")] == ["c2"]
