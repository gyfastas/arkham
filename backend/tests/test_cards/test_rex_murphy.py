"""Tests for Rex Murphy investigator ability."""

import pytest
from backend.cards.seeker.rex_murphy import RexMurphy
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def game():
    g = Game("test_rex")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="rex_murphy", name="Rex Murphy")
    g.register_card_data(inv_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)

    deck = ["card_a", "card_b", "card_c", "card_d", "card_e"] * 3
    g.add_investigator("rex", inv_data, deck=deck, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)

    return g


@pytest.fixture
def impl(game):
    impl = RexMurphy("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


def _investigate_success(game, modified_skill, difficulty):
    """模拟一次调查检定成功。"""
    _emit(game, GameEvent.INVESTIGATE_ACTION_INITIATED, investigator_id="rex")
    _emit(
        game, GameEvent.SKILL_TEST_SUCCESSFUL,
        investigator_id="rex", success=True,
        modified_skill=modified_skill, difficulty=difficulty,
    )


class TestRexMurphy:
    def test_discover_clue_on_success_by_two(self, game, impl):
        """调查成功2点以上：发现1个线索；每回合限1次，下回合重置。"""
        inv = game.state.get_investigator("rex")
        loc = game.state.locations["test_location"]

        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="rex")
        _investigate_success(game, modified_skill=5, difficulty=2)

        assert inv.clues == 1
        assert loc.clues == 2

        # 每回合限1次
        _investigate_success(game, modified_skill=6, difficulty=2)
        assert inv.clues == 1
        assert loc.clues == 2

        # 检定结束后跟踪状态清除；新回合限次重置
        _emit(game, GameEvent.SKILL_TEST_ENDS, investigator_id="rex")
        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="rex")
        _investigate_success(game, modified_skill=4, difficulty=2)
        assert inv.clues == 2
        assert loc.clues == 1

    def test_requires_margin_two_and_investigating(self, game, impl):
        """成功不足2点、或非调查检定时不触发。"""
        inv = game.state.get_investigator("rex")

        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="rex")

        # 只超过难度1点：不触发
        _investigate_success(game, modified_skill=3, difficulty=2)
        assert inv.clues == 0

        # 非调查检定（未发出 INVESTIGATE_ACTION_INITIATED）：不触发
        _emit(game, GameEvent.SKILL_TEST_ENDS, investigator_id="rex")
        _emit(
            game, GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="rex", success=True,
            modified_skill=6, difficulty=2,
        )
        assert inv.clues == 0

    def test_elder_sign_plus_two(self, game, impl):
        """远古印记：+2。"""
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="rex", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 2

    def test_elder_sign_choose_autofail_draws_three(self, game, impl):
        """预授权后远古印记改为：抽3张牌并（近似）自动失败。"""
        inv = game.state.get_investigator("rex")
        inv.deck = ["card_a", "card_b", "card_c", "card_d"]
        inv.hand = []

        assert impl.choose_autofail(game.state, "rex") is True

        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="rex", chaos_token=ChaosTokenType.ELDER_SIGN,
            amount=0,
        )
        assert ctx.amount == -1000
        assert ctx.extra["rex_murphy_chose_autofail"] is True
        assert inv.hand == ["card_a", "card_b", "card_c"]
        assert inv.deck == ["card_d"]
