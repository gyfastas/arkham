"""Tests for The 13th Vision (Level 0)."""

from backend.cards.neutral.the_13th_vision_lv0 import The13thVision
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent, Skill
from backend.tests.conftest import make_investigator_data


def _draw(game):
    impl = The13thVision("tv_1")
    impl.register(game.event_bus, "tv_1")
    inv = game.state.get_investigator("test_investigator")
    inv.hand.append("the_13th_vision_lv0")
    game.event_bus.emit(EventContext(
        game_state=game.state, event=GameEvent.CARD_DRAWN,
        investigator_id="test_investigator",
        extra={"card_id": "the_13th_vision_lv0"},
    ))
    return impl


def _success_ctx(game, inv_id, modified, difficulty):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
        investigator_id=inv_id, skill_type=Skill.INTELLECT,
        success=True, modified_skill=modified, difficulty=difficulty,
    )
    game.event_bus.emit(ctx)
    return ctx


class TestThe13thVision:
    def test_tie_fails_at_owner_location(self, game):
        """同地点调查员平局（技能值==难度）：失败。"""
        _draw(game)
        ctx = _success_ctx(game, "test_investigator", modified=3, difficulty=3)
        assert ctx.success is False
        assert ctx.extra["the_13th_vision_tie_failed"] is True

    def test_non_tie_untouched(self, game):
        """超过难度：不受影响。"""
        _draw(game)
        ctx = _success_ctx(game, "test_investigator", modified=5, difficulty=3)
        assert ctx.success is True
        assert "the_13th_vision_tie_failed" not in ctx.extra

    def test_other_location_untouched(self, game):
        """其他地点的调查员不受影响。"""
        _draw(game)
        other = make_investigator_data(id="inv2", name="Inv2")
        game.register_card_data(other)
        game.add_investigator("inv2", other, starting_location="somewhere_else")
        ctx = _success_ctx(game, "inv2", modified=3, difficulty=3)
        assert ctx.success is True

    def test_discard_activation(self, game):
        impl = _draw(game)
        inv = game.state.get_investigator("test_investigator")
        assert impl.activate_discard(game.state, "test_investigator") is True
        assert "the_13th_vision_lv0" in inv.discard
        # 丢弃后平局不再失败
        ctx = _success_ctx(game, "test_investigator", modified=3, difficulty=3)
        assert ctx.success is True
