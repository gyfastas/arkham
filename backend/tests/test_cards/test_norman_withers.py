"""Tests for Norman Withers investigator ability."""

import pytest
from backend.cards.seeker.norman_withers import NormanWithers
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent
from backend.tests.conftest import (
    make_asset_data, make_event_data, make_investigator_data,
    make_location_data, make_skill_data,
)


def _make_weakness(id="weakness_1"):
    from backend.models.enums import CardType as CT, PlayerClass
    from backend.models.state import CardData
    return CardData(
        id=id, name="Test Weakness", name_cn="测试弱点",
        type=CT.TREACHERY, card_class=PlayerClass.NEUTRAL,
        subtype="basic_weakness",
    )


@pytest.fixture
def game():
    g = Game("test_norman")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="norman_withers", name="Norman Withers")
    g.register_card_data(inv_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)

    g.register_card_data(make_asset_data(id="top_asset", name="Top Asset", cost=3))
    g.register_card_data(make_event_data(id="top_event", name="Top Event", cost=2))
    g.register_card_data(make_event_data(
        id="fast_event", name="Fast Event", cost=0, fast=True))
    g.register_card_data(make_skill_data(id="top_skill", name="Top Skill"))
    g.register_card_data(_make_weakness())
    g.register_card_data(_make_weakness("weakness_2"))

    deck = ["card_a", "card_b", "card_c", "card_d", "card_e"] * 3
    g.add_investigator("norman", inv_data, deck=deck,
                       starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)

    return g


@pytest.fixture
def impl(game):
    impl = NormanWithers("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


class TestNormanPlayTopCard:
    def test_play_top_asset_reduced_cost(self, game, impl):
        """打出牌堆顶支援：费用-1、消耗1行动、每轮限1次。"""
        inv = game.state.get_investigator("norman")
        inv.resources = 5
        inv.actions_remaining = 3
        inv.deck = ["top_asset"] + inv.deck

        assert impl.top_card(game.state, "norman") == "top_asset"
        assert impl.activate_play_top_card(game.state, "norman") is True
        assert inv.resources == 5 - 2  # 3费-1
        assert inv.actions_remaining == 2
        assert "top_asset" not in inv.deck
        inst = game.state.cards_in_play[inv.play_area[0]]
        assert inst.card_id == "top_asset"

        # 每轮限1次
        inv.deck.insert(0, "top_event")
        inv.resources = 5
        assert impl.activate_play_top_card(game.state, "norman") is False

        # 新一轮重置
        _emit(game, GameEvent.ROUND_BEGINS)
        assert impl.activate_play_top_card(game.state, "norman") is True
        assert inv.resources == 5 - 1  # 事件2费-1
        assert "top_event" in inv.discard

    def test_play_top_fast_event_no_action(self, game, impl):
        """fast 卡不消耗行动。"""
        inv = game.state.get_investigator("norman")
        inv.actions_remaining = 3
        inv.deck = ["fast_event"] + inv.deck
        assert impl.activate_play_top_card(game.state, "norman") is True
        assert inv.actions_remaining == 3
        assert "fast_event" in inv.discard

    def test_play_top_rejects_unplayable(self, game, impl):
        """技能卡/弱点/付不起费时不能打出。"""
        inv = game.state.get_investigator("norman")
        inv.deck = ["top_skill"] + inv.deck
        assert impl.activate_play_top_card(game.state, "norman") is False

        inv.deck = ["top_asset"] + inv.deck
        inv.resources = 1  # 3费-1=2 付不起
        assert impl.activate_play_top_card(game.state, "norman") is False


class TestNormanForcedWeaknessDraw:
    def test_weakness_on_top_drawn_after_card_drawn(self, game, impl):
        """抽牌后牌堆顶是弱点：强制抽取（可连锁）。"""
        inv = game.state.get_investigator("norman")
        inv.hand = []
        inv.deck = ["weakness_1", "weakness_2", "card_a"]

        _emit(game, GameEvent.CARD_DRAWN,
              investigator_id="norman", extra={"card_id": "card_x"})
        assert "weakness_1" in inv.hand
        assert "weakness_2" in inv.hand
        assert inv.deck == ["card_a"]

    def test_weakness_on_top_drawn_at_round_begins(self, game, impl):
        """每轮开始时牌堆顶是弱点也强制抽取。"""
        inv = game.state.get_investigator("norman")
        inv.hand = []
        inv.deck = ["weakness_1", "card_a"]
        _emit(game, GameEvent.ROUND_BEGINS)
        assert "weakness_1" in inv.hand
        assert inv.deck == ["card_a"]

    def test_non_weakness_top_not_drawn(self, game, impl):
        inv = game.state.get_investigator("norman")
        inv.hand = []
        inv.deck = ["card_a", "weakness_1"]
        _emit(game, GameEvent.ROUND_BEGINS)
        assert inv.hand == []
        assert inv.deck == ["card_a", "weakness_1"]


class TestNormanElderSign:
    def test_elder_sign_plus_x(self, game, impl):
        """远古印记：+X，X=牌堆顶卡牌资源费用。"""
        inv = game.state.get_investigator("norman")
        inv.deck = ["top_asset"] + inv.deck  # 3费
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="norman", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 3

        inv.deck = ["top_skill"] + inv.deck  # 无费用 → +0
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="norman", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 0

    def test_elder_sign_swap_with_hand(self, game, impl):
        """预设手牌交换牌堆顶：交换生效；换上弱点则立即强制抽取。"""
        inv = game.state.get_investigator("norman")
        inv.hand = ["card_a"]
        inv.deck = ["top_asset", "card_b"]

        assert impl.choose_elder_sign_swap(game.state, "norman", "card_a") is True
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="norman", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 3  # X 取交换前的牌堆顶费用
        assert inv.deck[0] == "card_a"
        assert "top_asset" in inv.hand
        assert "card_a" not in inv.hand

        # 换上弱点：强制能力立即将其抽回手牌
        inv.hand = ["weakness_1"]
        inv.deck = ["top_asset", "card_b"]
        impl.choose_elder_sign_swap(game.state, "norman", "weakness_1")
        _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="norman", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert "weakness_1" in inv.hand
        assert "top_asset" in inv.hand
        assert inv.deck == ["card_b"]

    def test_swap_preset_must_be_in_hand(self, game, impl):
        assert impl.choose_elder_sign_swap(game.state, "norman", "not_in_hand") is False
