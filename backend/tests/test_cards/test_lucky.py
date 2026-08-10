"""Tests for Lucky! (Level 0 and Level 2)."""

import pytest
from backend.cards.survivor.lucky_lv0 import Lucky
from backend.cards.survivor.lucky_lv2 import LuckyLv2
from backend.models.enums import PlayerClass
from backend.tests.conftest import make_investigator_data, make_location_data
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(Lucky)
    g.card_registry.register_class(LuckyLv2)
    return g


class TestLucky:
    def test_lv0_registered(self, game):
        assert "lucky_lv0" in game.card_registry.registered_cards

    def test_lv2_registered(self, game):
        assert "lucky_lv2" in game.card_registry.registered_cards


def _fail_ctx(game, *, difficulty, modified_skill):
    from backend.engine.event_bus import EventContext
    from backend.models.enums import GameEvent

    ctx = EventContext(
        game_state=game.state, event=GameEvent.SKILL_TEST_FAILED,
        investigator_id="inv1", success=False,
        difficulty=difficulty, modified_skill=modified_skill,
    )
    game.event_bus.emit(ctx)
    return ctx


class TestLuckyMargin:
    """卡面：失败后打出，+2 技能值——差值≤2 才能翻转。"""

    def _setup(self, game, card_id="lucky_lv0", impl=None, resources=1):
        if impl is not None:
            instance = impl(f"impl_{card_id}")
            instance.register(game.event_bus, f"impl_{card_id}")
        inv = game.state.get_investigator("inv1")
        inv.hand = [card_id]
        inv.resources = resources
        return inv

    def test_fail_by_1_flips_to_success(self, game):
        inv = self._setup(game, impl=Lucky)
        ctx = _fail_ctx(game, difficulty=4, modified_skill=3)
        assert ctx.success is True
        assert "lucky_lv0" in inv.discard
        assert inv.resources == 0

    def test_fail_by_2_flips_to_success(self, game):
        inv = self._setup(game, impl=Lucky)
        ctx = _fail_ctx(game, difficulty=4, modified_skill=2)
        assert ctx.success is True

    def test_fail_by_3_still_fails(self, game):
        inv = self._setup(game, impl=Lucky)
        ctx = _fail_ctx(game, difficulty=5, modified_skill=2)
        assert ctx.success is False
        # 卡仍然打出并消耗
        assert "lucky_lv0" in inv.discard
        assert inv.resources == 0

    def test_lv2_draws_a_card_on_play(self, game):
        """lv2 卡面：+2 技能值，并抽1张牌（无论成败，不返回手牌）。"""
        inv = self._setup(game, card_id="lucky_lv2", impl=LuckyLv2)
        inv.deck = ["deck_card_a"]
        ctx = _fail_ctx(game, difficulty=4, modified_skill=3)
        assert ctx.success is True
        assert "deck_card_a" in inv.hand
        assert "lucky_lv2" in inv.discard

        inv2 = self._setup(game, card_id="lucky_lv2", impl=LuckyLv2)
        inv2.deck = ["deck_card_b"]
        ctx = _fail_ctx(game, difficulty=6, modified_skill=2)
        assert ctx.success is False
        # 失败同样抽牌
        assert "deck_card_b" in inv2.hand
        assert "lucky_lv2" in inv2.discard
