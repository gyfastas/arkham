"""Tests for Live and Learn (Level 0)."""

import pytest
from backend.cards.survivor.live_and_learn_lv0 import LiveAndLearn
from backend.models.enums import GameEvent
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)
from backend.engine.event_bus import EventContext
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="live_and_learn_lv0", name="Live and Learn", cost=0))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(LiveAndLearn)
    impl = LiveAndLearn("impl_live_and_learn")
    impl.register(g.event_bus, "impl_live_and_learn")
    return g


def _fail_ctx(game, *, difficulty, modified_skill):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.SKILL_TEST_FAILED,
        investigator_id="inv1", success=False,
        difficulty=difficulty, modified_skill=modified_skill,
    )
    game.event_bus.emit(ctx)
    return ctx


class TestLiveAndLearn:
    def test_card_registered(self, game):
        assert "live_and_learn_lv0" in game.card_registry.registered_cards

    def test_fail_by_2_or_less_flips_to_success(self, game):
        """失败后自动打出：+2重试，差值≤2翻转成功。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["live_and_learn_lv0"]

        ctx = _fail_ctx(game, difficulty=5, modified_skill=3)

        assert ctx.success is True
        assert "live_and_learn_lv0" in inv.discard
        assert "live_and_learn_lv0" not in inv.hand

    def test_fail_by_3_still_fails(self, game):
        inv = game.state.get_investigator("inv1")
        inv.hand = ["live_and_learn_lv0"]

        ctx = _fail_ctx(game, difficulty=6, modified_skill=3)

        assert ctx.success is False
        assert "live_and_learn_lv0" in inv.discard  # 卡已消耗

    def test_no_trigger_without_card_in_hand(self, game):
        ctx = _fail_ctx(game, difficulty=4, modified_skill=3)
        assert ctx.success is False
