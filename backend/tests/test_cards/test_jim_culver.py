"""Tests for Jim Culver investigator ability."""

import pytest
from backend.cards.mystic.jim_culver import JimCulver
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def game():
    g = Game("test_jim")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="jim_culver", name="Jim Culver")
    g.register_card_data(inv_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)

    deck = ["card_a", "card_b", "card_c", "card_d", "card_e"] * 3
    g.add_investigator("jim", inv_data, deck=deck, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)

    return g


@pytest.fixture
def impl(game):
    impl = JimCulver("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


class TestJimCulver:
    def test_skull_treated_as_zero(self, game, impl):
        """骷髅标记修正值视为0（即使场景把它改成-2）。"""
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="jim", chaos_token=ChaosTokenType.SKULL,
            amount=-2,
        )
        assert ctx.amount == 0

    def test_skull_not_modified_for_other_investigator(self, game, impl):
        """非 Jim 的调查员不受影响。"""
        inv_data = make_investigator_data(id="roland_banks", name="Roland Banks")
        game.register_card_data(inv_data)
        game.add_investigator("roland", inv_data, starting_location="test_location")

        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="roland", chaos_token=ChaosTokenType.SKULL,
            amount=-2,
        )
        assert ctx.amount == -2

    def test_elder_sign_plus_one(self, game, impl):
        """远古印记：+1。"""
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="jim", chaos_token=ChaosTokenType.ELDER_SIGN,
            amount=0,
        )
        assert ctx.amount == 1

    def test_choose_skull_instead(self, game, impl):
        """预授权后远古印记视为骷髅（修正为0），且只生效一次。"""
        assert impl.choose_skull_instead(game.state, "jim") is True

        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="jim", chaos_token=ChaosTokenType.ELDER_SIGN,
            amount=0,
        )
        assert ctx.amount == 0
        assert ctx.extra["jim_culver_treated_as_skull"] is True

        # 第二次远古印记恢复 +1
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="jim", chaos_token=ChaosTokenType.ELDER_SIGN,
            amount=0,
        )
        assert ctx.amount == 1

    def test_armed_state_cleared_on_test_end(self, game, impl):
        """检定结束时清除预授权状态。"""
        impl.choose_skull_instead(game.state, "jim")
        _emit(game, GameEvent.SKILL_TEST_ENDS, investigator_id="jim")

        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="jim", chaos_token=ChaosTokenType.ELDER_SIGN,
            amount=0,
        )
        assert ctx.amount == 1

    def test_deck_requirements_include_any_class_level0_slots(self):
        """02004：构筑选项含"任意阵营0级至多5张"（ mystic/neutral 0-5 之外）。"""
        import json
        from pathlib import Path
        path = (Path(__file__).resolve().parents[3]
                / "data" / "investigators" / "jim_culver.json")
        req = json.loads(path.read_text(encoding="utf-8"))["deck_requirements"]
        assert req["cards"]["mystic"] == {"min_level": 0, "max_level": 5}
        assert req["cards"]["neutral"] == {"min_level": 0, "max_level": 5}
        assert req["cards"]["any"] == {
            "min_level": 0, "max_level": 0, "max_count": 5,
        }
