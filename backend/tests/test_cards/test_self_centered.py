"""Tests for Self-Centered (Level 0)."""

from backend.cards.neutral.self_centered_lv0 import SelfCentered
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent


def _draw(game):
    impl = SelfCentered("sc_1")
    impl.register(game.event_bus, "sc_1")
    inv = game.state.get_investigator("test_investigator")
    inv.hand.append("self_centered_lv0")
    game.event_bus.emit(EventContext(
        game_state=game.state, event=GameEvent.CARD_DRAWN,
        investigator_id="test_investigator",
        extra={"card_id": "self_centered_lv0"},
    ))
    return impl


class TestSelfCentered:
    def test_revelation_to_threat_area(self, game):
        _draw(game)
        inv = game.state.get_investigator("test_investigator")
        inst = game.state.get_card_instance(inv.threat_area[0])
        assert inst.card_id == "self_centered_lv0"
        assert "self_centered_lv0" not in inv.hand

    def test_cannot_commit_to_others(self, game):
        """在场时：不能向其他调查员检定投入卡牌/影响其他调查员。"""
        impl = _draw(game)
        assert impl.can_commit_to_others(game.state, "test_investigator") is False
        assert impl.can_affect_others(game.state, "test_investigator") is False

    def test_discard_activation(self, game):
        """[行动×2]：丢弃。"""
        impl = _draw(game)
        inv = game.state.get_investigator("test_investigator")
        assert impl.activate_discard(game.state, "test_investigator") is True
        assert inv.threat_area == []
        assert "self_centered_lv0" in inv.discard
        assert impl.can_commit_to_others(game.state, "test_investigator") is True
