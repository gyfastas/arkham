"""Tests for Lily Chen investigator ability."""

import pytest
from backend.cards.mystic.lily_chen import LilyChen
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_lily")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="lily_chen", name="Lily Chen")
    g.register_card_data(inv_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)

    g.register_card_data(make_asset_data(
        id="discipline_lv0", name="Discipline", cost=None))

    deck = ["discipline_lv0", "card_a", "discipline_lv0",
            "card_b", "card_c", "card_d"]
    g.add_investigator("lily", inv_data, deck=deck, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)

    return g


@pytest.fixture
def impl(game):
    impl = LilyChen("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


def _disciplines_in_play(game, inv):
    return [iid for iid in inv.play_area
            if game.state.cards_in_play[iid].card_id == "discipline_lv0"]


class TestLilySetup:
    def test_setup_disciplines_enters_play(self, game, impl):
        """游戏开始：牌库中所有演武入场（运功面），从牌库移除；幂等。"""
        inv = game.state.get_investigator("lily")
        placed = impl.setup_disciplines(game.state, "lily")
        assert len(placed) == 2
        assert len(_disciplines_in_play(game, inv)) == 2
        assert "discipline_lv0" not in inv.deck
        # 运功面：无破损标记
        for iid in placed:
            assert f"discipline_broken_{iid}" not in game.state.scenario.vars

        # 幂等：再次调用不再入场
        assert impl.setup_disciplines(game.state, "lily") == []

    def test_round_begins_fallback(self, game, impl):
        """第一轮开始兜底入场。"""
        inv = game.state.get_investigator("lily")
        _emit(game, GameEvent.ROUND_BEGINS)
        assert len(_disciplines_in_play(game, inv)) == 2
        assert "discipline_lv0" not in inv.deck


class TestLilyElderSign:
    def test_elder_sign_plus_two_no_broken(self, game, impl):
        """无破损演武：仅 +2。"""
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="lily", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 2
        _emit(game, GameEvent.SKILL_TEST_ENDS, investigator_id="lily")

    def test_elder_sign_flips_broken_discipline(self, game, impl):
        """检定结束后：第一张可翻回的破损演武翻回运功面。"""
        inv = game.state.get_investigator("lily")
        placed = impl.setup_disciplines(game.state, "lily")
        # 上一轮破损（burden_of_destiny 约定：值为破损轮数）
        game.state.scenario.round_number = 2
        game.state.scenario.vars[f"discipline_broken_{placed[0]}"] = 1

        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="lily", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 2
        # 翻回发生在检定结束后
        assert f"discipline_broken_{placed[0]}" in game.state.scenario.vars
        _emit(game, GameEvent.SKILL_TEST_ENDS, investigator_id="lily")
        assert f"discipline_broken_{placed[0]}" not in game.state.scenario.vars

    def test_cannot_flip_back_same_round_as_broken(self, game, impl):
        """本轮刚破损的演武不能翻回（命运重担限制）。"""
        inv = game.state.get_investigator("lily")
        placed = impl.setup_disciplines(game.state, "lily")
        game.state.scenario.round_number = 3
        game.state.scenario.vars[f"discipline_broken_{placed[0]}"] = 3  # 本轮破损

        _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="lily", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        _emit(game, GameEvent.SKILL_TEST_ENDS, investigator_id="lily")
        assert f"discipline_broken_{placed[0]}" in game.state.scenario.vars

    def test_flips_first_available_skipping_same_round(self, game, impl):
        """多张破损：跳过本轮破损的，翻回较早破损的。"""
        inv = game.state.get_investigator("lily")
        placed = impl.setup_disciplines(game.state, "lily")
        game.state.scenario.round_number = 3
        game.state.scenario.vars[f"discipline_broken_{placed[0]}"] = 3
        game.state.scenario.vars[f"discipline_broken_{placed[1]}"] = 1

        _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="lily", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        _emit(game, GameEvent.SKILL_TEST_ENDS, investigator_id="lily")
        assert f"discipline_broken_{placed[0]}" in game.state.scenario.vars
        assert f"discipline_broken_{placed[1]}" not in game.state.scenario.vars

    def test_non_elder_sign_no_flip(self, game, impl):
        """非远古印记不翻回。"""
        inv = game.state.get_investigator("lily")
        placed = impl.setup_disciplines(game.state, "lily")
        game.state.scenario.round_number = 2
        game.state.scenario.vars[f"discipline_broken_{placed[0]}"] = 1

        _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="lily", chaos_token=ChaosTokenType.SKULL, amount=-1,
        )
        _emit(game, GameEvent.SKILL_TEST_ENDS, investigator_id="lily")
        assert f"discipline_broken_{placed[0]}" in game.state.scenario.vars
