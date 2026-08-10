"""Tests for Sister Mary investigator ability and elder sign."""

import pytest

from backend.cards.guardian.sister_mary import SisterMary
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.chaos import STANDARD_BAG
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.tests.conftest import (
    make_investigator_data, make_location_data,
)


def _bless_count(bag) -> int:
    return sum(1 for t in bag.tokens if t == ChaosTokenType.BLESS)


@pytest.fixture
def game():
    g = Game("test_mary")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="sister_mary", name="Sister Mary", willpower=4)
    g.register_card_data(inv_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)

    g.add_investigator("mary", inv_data, deck=["card_a"] * 10, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)
    return g


@pytest.fixture
def impl(game):
    impl = SisterMary("test_instance")
    impl.register(game.event_bus, "test_instance")
    impl.bind_chaos_bag(game.chaos_bag)
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


class TestSisterMarySetup:
    def test_setup_adds_two_bless_tokens(self, game, impl):
        """设置期间：加入2个祝福标记到混乱袋。"""
        assert _bless_count(game.chaos_bag) == 2
        # 其余标记不受影响
        assert len(game.chaos_bag.tokens) == len(STANDARD_BAG) + 2

    def test_setup_via_game_setup_activation(self):
        """Game.setup() 自动激活调查员实现时即加入2个祝福标记（生产路径）。"""
        g = Game("test_mary_setup")
        inv_data = make_investigator_data(id="sister_mary", name="Sister Mary")
        g.register_card_data(inv_data)
        loc_data = make_location_data()
        g.register_card_data(loc_data)
        g.add_investigator(
            "mary", inv_data, deck=["card_a"] * 10, starting_location="test_location",
        )
        g.add_location("test_location", loc_data, clues=3)

        g.setup()
        assert _bless_count(g.chaos_bag) == 2

    def test_bind_is_idempotent(self, game, impl):
        """重复绑定不重复加入祝福标记。"""
        impl.bind_chaos_bag(game.chaos_bag)
        assert _bless_count(game.chaos_bag) == 2


class TestSisterMaryRoundEnd:
    def test_round_end_adds_bless(self, game, impl):
        """一轮结束时：加入1个祝福标记。"""
        before = _bless_count(game.chaos_bag)
        _emit(game, GameEvent.ROUND_ENDS)
        assert _bless_count(game.chaos_bag) == before + 1


class TestSisterMaryElderSign:
    def test_elder_sign_success_adds_bless(self, game, impl):
        """远古印记：+1；检定成功时加入1个祝福标记（走真实检定流程）。"""
        game.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        before = _bless_count(game.chaos_bag)

        result = game.skill_test_engine.run_test("mary", Skill.WILLPOWER, 2)

        assert result.token == ChaosTokenType.ELDER_SIGN
        assert result.token_modifier == 1  # +1
        assert result.success
        assert _bless_count(game.chaos_bag) == before + 1

    def test_elder_sign_failure_adds_nothing(self, game, impl):
        """远古印记检定失败：不加入祝福标记。"""
        game.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        before = _bless_count(game.chaos_bag)

        result = game.skill_test_engine.run_test("mary", Skill.WILLPOWER, 99)

        assert not result.success
        assert _bless_count(game.chaos_bag) == before

    def test_no_effect_for_other_investigators(self, game, impl):
        """其他调查员揭示远古印记不触发。"""
        other_data = make_investigator_data(id="other_inv", name="Other")
        game.register_card_data(other_data)
        game.add_investigator("other", other_data, deck=[], starting_location="test_location")

        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="other", chaos_token=ChaosTokenType.ELDER_SIGN,
            skill_type=Skill.WILLPOWER,
        )
        assert ctx.amount == 0
        before = _bless_count(game.chaos_bag)
        _emit(game, GameEvent.SKILL_TEST_SUCCESSFUL, investigator_id="other",
              skill_type=Skill.WILLPOWER)
        assert _bless_count(game.chaos_bag) == before
