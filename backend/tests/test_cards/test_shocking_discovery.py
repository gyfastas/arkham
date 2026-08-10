"""Tests for Shocking Discovery (Level 0)."""

from backend.cards.neutral.shocking_discovery_lv0 import ShockingDiscovery
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent


def _register(game):
    impl = ShockingDiscovery("sd_1")
    impl.register(game.event_bus, "sd_1")
    return impl


class TestShockingDiscovery:
    def test_revelation_shuffles_back(self, game):
        """显现：洗回牌组。"""
        _register(game)
        inv = game.state.get_investigator("test_investigator")
        inv.hand.append("shocking_discovery_lv0")
        inv.deck = ["card_a", "card_b"]

        ctx = EventContext(
            game_state=game.state, event=GameEvent.CARD_DRAWN,
            investigator_id="test_investigator",
            extra={"card_id": "shocking_discovery_lv0"},
        )
        game.event_bus.emit(ctx)
        assert ctx.extra["shocking_discovery_shuffled"] is True
        assert "shocking_discovery_lv0" in inv.deck
        assert "shocking_discovery_lv0" not in inv.hand
        assert "shocking_discovery_lv0" not in inv.discard
        assert len(inv.deck) == 3

    def test_on_searched(self, game):
        """被检索到时：丢弃、混洗牌组、抽遭遇牌堆顶。"""
        impl = _register(game)
        inv = game.state.get_investigator("test_investigator")
        inv.deck = ["card_a", "shocking_discovery_lv0", "card_b"]
        game.state.scenario.encounter_deck = ["enc_1"]

        drawn = []
        game.event_bus.register(
            GameEvent.ENCOUNTER_CARD_DRAWN,
            lambda ctx: drawn.append(ctx.extra.get("card_id")),
        )
        assert impl.on_searched(game.state, "test_investigator") is True
        assert "shocking_discovery_lv0" in inv.discard
        assert "shocking_discovery_lv0" not in inv.deck
        assert sorted(inv.deck) == ["card_a", "card_b"]
        assert drawn == ["enc_1"]
        assert game.state.scenario.encounter_deck == []
