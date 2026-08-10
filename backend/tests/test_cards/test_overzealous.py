"""Tests for Overzealous (Level 0) — Neutral basic weakness."""

from backend.cards.neutral.overzealous_lv0 import Overzealous
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent


def _draw(game):
    Overzealous("o1").register(game.event_bus, "o1")
    inv = game.state.get_investigator("test_investigator")
    inv.hand.append("overzealous_lv0")
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_DRAWN,
        investigator_id="test_investigator",
        extra={"card_id": "overzealous_lv0"},
    )
    game.event_bus.emit(ctx)
    return ctx, inv


class TestOverzealous:
    def test_draws_two_with_surge(self, game):
        """抽遭遇牌堆顶1张 + 涌动再抽1张，均入遭遇弃牌堆。"""
        game.state.scenario.encounter_deck = ["enc_a", "enc_b", "enc_c"]
        ctx, inv = _draw(game)

        assert ctx.extra["overzealous_drawn"] == ["enc_a", "enc_b"]
        assert game.state.scenario.encounter_discard == ["enc_a", "enc_b"]
        assert game.state.scenario.encounter_deck == ["enc_c"]
        assert "overzealous_lv0" not in inv.hand
        assert "overzealous_lv0" in inv.discard

    def test_empty_encounter_deck_draws_nothing(self, game):
        game.state.scenario.encounter_deck = []
        ctx, inv = _draw(game)
        assert ctx.extra["overzealous_drawn"] == []
        assert "overzealous_lv0" in inv.discard

    def test_single_card_deck_no_surge_draw(self, game):
        """牌堆只剩1张时涌动无卡可抽。"""
        game.state.scenario.encounter_deck = ["enc_a"]
        ctx, inv = _draw(game)
        assert ctx.extra["overzealous_drawn"] == ["enc_a"]
