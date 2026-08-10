"""Tests for Rational Thought (Level 0) — Carolyn Fern weakness."""

from backend.cards.neutral.rational_thought_lv0 import RationalThought
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent


def _draw(game):
    impl = RationalThought("rt_1")
    impl.register(game.event_bus, "rt_1")
    inv = game.state.get_investigator("test_investigator")
    inv.hand.append("rational_thought_lv0")
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_DRAWN,
        investigator_id="test_investigator",
        extra={"card_id": "rational_thought_lv0"},
    )
    game.event_bus.emit(ctx)
    return impl


class TestRationalThought:
    def test_revelation_places_with_four_horror(self, game):
        """显现：入威胁区，上置4恐惧。"""
        _draw(game)
        inv = game.state.get_investigator("test_investigator")
        inst = game.state.get_card_instance(inv.threat_area[0])
        assert inst.card_id == "rational_thought_lv0"
        assert inst.horror == 4
        assert "rational_thought_lv0" not in inv.hand

    def test_heal_horror_and_discard_at_zero(self, game):
        """治疗本卡恐惧；清零即丢弃。"""
        impl = _draw(game)
        inv = game.state.get_investigator("test_investigator")
        assert impl.heal_horror(game.state, "test_investigator", amount=1) is True
        inst = game.state.get_card_instance(inv.threat_area[0])
        assert inst.horror == 3
        # 清零 → 丢弃
        assert impl.heal_horror(game.state, "test_investigator", amount=3) is True
        assert inv.threat_area == []
        assert "rational_thought_lv0" in inv.discard

    def test_cannot_heal_other_horror_or_gain_reaction_resources(self, game):
        """在场时：不能治疗其他卡恐惧，不能从卡洛琳反应获资源。"""
        impl = _draw(game)
        assert impl.can_heal_other_horror(game.state, "test_investigator") is False
        assert impl.can_gain_reaction_resources(game.state, "test_investigator") is False
