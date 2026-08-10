"""Tests for The Bell Tolls (Level 0)."""

from backend.cards.neutral.the_bell_tolls_lv0 import TheBellTolls
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent


class TestTheBellTolls:
    def test_revelation_kills_investigator(self, game):
        """显现：持有者被杀死（致命伤害 + INVESTIGATOR_DEFEATED）。"""
        impl = TheBellTolls("bt_1")
        impl.register(game.event_bus, "bt_1")
        inv = game.state.get_investigator("test_investigator")
        inv.hand.append("the_bell_tolls_lv0")

        defeated = []
        game.event_bus.register(
            GameEvent.INVESTIGATOR_DEFEATED,
            lambda ctx: defeated.append(ctx.extra.get("killed")),
        )
        ctx = EventContext(
            game_state=game.state, event=GameEvent.CARD_DRAWN,
            investigator_id="test_investigator",
            extra={"card_id": "the_bell_tolls_lv0"},
        )
        game.event_bus.emit(ctx)

        assert inv.damage >= inv.health
        assert inv.is_defeated is True
        assert defeated == [True]
        assert ctx.extra["the_bell_tolls_killed"] is True
        assert "the_bell_tolls_lv0" in inv.discard
        assert "the_bell_tolls_lv0" not in inv.hand
