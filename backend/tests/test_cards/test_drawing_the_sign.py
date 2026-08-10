"""Tests for Drawing the Sign (Level 0) — Neutral basic weakness."""

from backend.cards.neutral.drawing_the_sign_lv0 import DrawingTheSign
from backend.engine.event_bus import EventContext
from backend.engine.phase_upkeep import HAND_SIZE_LIMIT
from backend.models.enums import GameEvent


def _reveal(game):
    impl = DrawingTheSign("d1")
    impl.register(game.event_bus, "d1")
    inv = game.state.get_investigator("test_investigator")
    inv.hand.append("drawing_the_sign_lv0")
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_DRAWN,
        investigator_id="test_investigator",
        extra={"card_id": "drawing_the_sign_lv0"},
    )
    game.event_bus.emit(ctx)
    return impl, inv


class TestDrawingTheSign:
    def test_revelation_enters_threat_area(self, game):
        impl, inv = _reveal(game)
        assert "drawing_the_sign_lv0" not in inv.hand
        assert len(inv.threat_area) == 1
        inst = game.state.get_card_instance(inv.threat_area[0])
        assert inst.card_id == "drawing_the_sign_lv0"

    def test_hand_size_reduced_by_5(self, game):
        """UPKEEP 手牌上限 8 → 3。"""
        impl, inv = _reveal(game)
        ctx = EventContext(
            game_state=game.state, event=GameEvent.UPKEEP_PHASE_BEGINS,
            investigator_id="test_investigator", amount=HAND_SIZE_LIMIT,
        )
        game.event_bus.emit(ctx)
        assert ctx.amount == HAND_SIZE_LIMIT - 5

    def test_no_reduction_for_other_investigator(self, game):
        impl, inv = _reveal(game)
        ctx = EventContext(
            game_state=game.state, event=GameEvent.UPKEEP_PHASE_BEGINS,
            investigator_id="someone_else", amount=HAND_SIZE_LIMIT,
        )
        game.event_bus.emit(ctx)
        assert ctx.amount == HAND_SIZE_LIMIT

    def test_activate_discard(self, game):
        """[行动×2]丢弃后不再减手牌上限。"""
        impl, inv = _reveal(game)
        assert impl.activate_discard(game.state, "test_investigator") is True
        assert inv.threat_area == []
        assert "drawing_the_sign_lv0" in inv.discard

        ctx = EventContext(
            game_state=game.state, event=GameEvent.UPKEEP_PHASE_BEGINS,
            investigator_id="test_investigator", amount=HAND_SIZE_LIMIT,
        )
        game.event_bus.emit(ctx)
        assert ctx.amount == HAND_SIZE_LIMIT
        # 不在威胁区时不可再丢弃
        assert impl.activate_discard(game.state, "test_investigator") is False
