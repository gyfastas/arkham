"""Tests for Wendy Adams investigator ability."""

import pytest
from backend.cards.survivor.wendy_adams import WendyAdams
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_wendy")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="wendy_adams", name="Wendy Adams")
    g.register_card_data(inv_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)

    amulet_data = make_asset_data(id="wendys_amulet", name="Wendy's Amulet")
    g.register_card_data(amulet_data)

    deck = ["card_a", "card_b", "card_c", "card_d", "card_e"] * 3
    g.add_investigator("wendy", inv_data, deck=deck, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)

    return g


@pytest.fixture
def impl(game):
    impl = WendyAdams("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


class TestWendyAdams:
    def test_pending_choice_on_token_reveal_once_per_test(self, game, impl):
        """揭示混沌标记时设置 pending_choice；每次检定限1次。"""
        inv = game.state.get_investigator("wendy")
        inv.hand = ["card_a", "card_b"]

        _emit(game, GameEvent.SKILL_TEST_BEGINS, investigator_id="wendy")
        _emit(
            game, GameEvent.CHAOS_TOKEN_REVEALED,
            investigator_id="wendy", chaos_token=ChaosTokenType.MINUS_2,
        )

        pending = game.state.scenario.vars.get("pending_choice")
        assert pending is not None
        assert pending["kind"] == "wendy_adams_token_cancel"
        assert pending["investigator_id"] == "wendy"
        option_ids = [o["id"] for o in pending["options"]]
        assert "card_a" in option_ids
        assert "card_b" in option_ids
        assert "decline" in option_ids

        # 每次检定限1次：清除后同一次检定不再提供
        game.state.scenario.vars.pop("pending_choice")
        _emit(
            game, GameEvent.CHAOS_TOKEN_REVEALED,
            investigator_id="wendy", chaos_token=ChaosTokenType.MINUS_3,
        )
        assert game.state.scenario.vars.get("pending_choice") is None

        # 新检定：重新提供
        _emit(game, GameEvent.SKILL_TEST_BEGINS, investigator_id="wendy")
        _emit(
            game, GameEvent.CHAOS_TOKEN_REVEALED,
            investigator_id="wendy", chaos_token=ChaosTokenType.MINUS_3,
        )
        assert game.state.scenario.vars.get("pending_choice") is not None

    def test_no_pending_choice_for_other_investigators(self, game, impl):
        """其他调查员揭示标记时不提供选择。"""
        other_data = make_investigator_data(id="other_investigator", name="Other")
        game.register_card_data(other_data)
        game.add_investigator("other", other_data, deck=[], starting_location="test_location")
        other = game.state.get_investigator("other")
        other.hand = ["card_a"]

        _emit(
            game, GameEvent.CHAOS_TOKEN_REVEALED,
            investigator_id="other", chaos_token=ChaosTokenType.MINUS_2,
        )
        assert game.state.scenario.vars.get("pending_choice") is None

    def test_cancel_and_redraw(self, game, impl):
        """弃1张手牌取消标记并重抽：修正值替换为新标记的值。"""
        inv = game.state.get_investigator("wendy")
        inv.hand = ["card_a", "card_b"]
        impl.redraw_provider = lambda: ChaosTokenType.PLUS_1

        _emit(game, GameEvent.SKILL_TEST_BEGINS, investigator_id="wendy")
        _emit(
            game, GameEvent.CHAOS_TOKEN_REVEALED,
            investigator_id="wendy", chaos_token=ChaosTokenType.MINUS_2,
        )

        assert impl.resolve_cancel(game.state, "wendy", "card_a") is True
        assert "card_a" not in inv.hand
        assert "card_a" in inv.discard
        assert game.state.scenario.vars.get("pending_choice") is None

        # 原标记为 -2，重抽为 +1 → 修正值替换为 +1
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="wendy", chaos_token=ChaosTokenType.MINUS_2,
            amount=-2,
        )
        assert ctx.amount == 1
        assert ctx.extra["wendy_adams_redrawn_token"] == ChaosTokenType.PLUS_1

    def test_elder_sign_with_amulet_auto_success(self, game, impl):
        """远古印记：+0；温蒂的护身符在场时改为自动成功（+999 近似）。"""
        inv = game.state.get_investigator("wendy")

        amulet = CardInstance(
            instance_id="amulet_1", card_id="wendys_amulet",
            owner_id="wendy", controller_id="wendy",
        )
        game.state.cards_in_play["amulet_1"] = amulet
        inv.play_area.append("amulet_1")

        _emit(game, GameEvent.SKILL_TEST_BEGINS, investigator_id="wendy")
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="wendy", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        # +0：修正值不变
        assert ctx.amount == 0

        # 技能值确定时应用"自动成功"
        ctx2 = _emit(
            game, GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="wendy", amount=3,
        )
        assert ctx2.amount == 3 + 999

    def test_elder_sign_without_amulet_is_plus_zero(self, game, impl):
        """没有护身符时远古印记仅为 +0，无自动成功。"""
        _emit(game, GameEvent.SKILL_TEST_BEGINS, investigator_id="wendy")
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="wendy", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 0

        ctx2 = _emit(
            game, GameEvent.SKILL_VALUE_DETERMINED,
            investigator_id="wendy", amount=3,
        )
        assert ctx2.amount == 3
