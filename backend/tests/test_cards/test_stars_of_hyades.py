"""Tests for Stars of Hyades (Level 0) — Sefina Rousseau signature weakness."""

from backend.cards.neutral.stars_of_hyades_lv0 import StarsOfHyades
from backend.engine.event_bus import EventContext
from backend.models.enums import CardType, GameEvent
from backend.models.state import CardData
from backend.tests.conftest import make_asset_data, make_event_data


def _reveal(game, beneath, deck_size):
    StarsOfHyades("s1").register(game.event_bus, "s1")
    inv = game.state.get_investigator("test_investigator")
    inv.hand.append("stars_of_hyades_lv0")
    inv.deck = [f"d{i}" for i in range(deck_size)]
    game.state.scenario.vars["beneath_test_investigator"] = list(beneath)
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_DRAWN,
        investigator_id="test_investigator",
        extra={"card_id": "stars_of_hyades_lv0"},
    )
    game.event_bus.emit(ctx)
    return ctx, inv


class TestStarsOfHyades:
    def test_removes_event_beneath_and_shuffles_back(self, game):
        """赛菲娜下有事件：移除该事件；牌组≥5 → 重洗回牌组。"""
        game.register_card_data(make_event_data(id="event_a"))
        game.register_card_data(make_asset_data(id="asset_b"))
        ctx, inv = _reveal(game, beneath=["asset_b", "event_a"], deck_size=6)

        extra = ctx.extra["stars_of_hyades"]
        assert extra["removed"] == "event_a"
        removed = game.state.scenario.vars["removed_from_game"]
        assert removed == ["event_a"]
        assert game.state.scenario.vars["beneath_test_investigator"] == ["asset_b"]
        assert extra["shuffled_back"] is True
        assert "stars_of_hyades_lv0" in inv.deck
        assert len(inv.deck) == 7
        assert inv.damage == 0 and inv.horror == 0

    def test_no_event_takes_damage_and_horror(self, game):
        """赛菲娜下无事件：受1伤害1恐惧；牌组<5 → 入弃牌堆。"""
        ctx, inv = _reveal(game, beneath=[], deck_size=3)
        extra = ctx.extra["stars_of_hyades"]
        assert extra["removed"] is None
        assert inv.damage == 1 and inv.horror == 1
        assert extra["shuffled_back"] is False
        assert "stars_of_hyades_lv0" in inv.discard

    def test_only_assets_beneath_counts_as_no_event(self, game):
        game.register_card_data(make_asset_data(id="asset_b"))
        ctx, inv = _reveal(game, beneath=["asset_b"], deck_size=6)
        assert ctx.extra["stars_of_hyades"]["removed"] is None
        assert inv.damage == 1
