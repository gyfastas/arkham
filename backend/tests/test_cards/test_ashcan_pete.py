"""Tests for Ashcan Pete investigator ability."""

import pytest
from backend.cards.survivor.ashcan_pete import AshcanPete, DUKE_CARD_ID
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data,
    make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_pete")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="ashcan_pete", name='"Ashcan" Pete')
    g.register_card_data(inv_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)

    deck = ["card_a", "card_b", "card_c", "card_d", "card_e"] * 3
    g.add_investigator("pete", inv_data, deck=deck, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)

    return g


@pytest.fixture
def impl(game):
    impl = AshcanPete("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


def _add_exhausted_asset(game, inv_id="pete", instance_id="asset_1"):
    asset_data = make_asset_data(id="leather_coat_lv0")
    game.register_card_data(asset_data)
    asset = CardInstance(
        instance_id=instance_id, card_id="leather_coat_lv0",
        owner_id=inv_id, controller_id=inv_id,
    )
    asset.exhausted = True
    game.state.cards_in_play[instance_id] = asset
    game.state.get_investigator(inv_id).play_area.append(instance_id)
    return asset


class TestAshcanPete:
    def test_duke_enters_play_on_first_round(self, game, impl):
        """第一轮开始时杜克自动入场（幂等）。"""
        _emit(game, GameEvent.ROUND_BEGINS)
        inv = game.state.get_investigator("pete")
        duke_ids = [
            iid for iid in inv.play_area
            if game.state.get_card_instance(iid).card_id == DUKE_CARD_ID
        ]
        assert len(duke_ids) == 1

        # 再次触发不重复入场
        _emit(game, GameEvent.ROUND_BEGINS)
        duke_ids = [
            iid for iid in inv.play_area
            if game.state.get_card_instance(iid).card_id == DUKE_CARD_ID
        ]
        assert len(duke_ids) == 1

    def test_setup_duke_idempotent(self, game, impl):
        """setup_duke() 幂等。"""
        first = impl.setup_duke(game.state, "pete")
        second = impl.setup_duke(game.state, "pete")
        assert first is not None and first == second

    def test_ready_asset_discards_card_and_readies(self, game, impl):
        """[fast]弃1张手牌准备1张已横置的支援卡，每轮限1次。"""
        inv = game.state.get_investigator("pete")
        inv.hand = ["card_a"]
        asset = _add_exhausted_asset(game)

        assert impl.activate_ready_asset(game.state, "pete", "card_a", "asset_1") is True
        assert asset.exhausted is False
        assert "card_a" not in inv.hand
        assert "card_a" in inv.discard

        # 每轮限1次
        asset.exhausted = True
        inv.hand = ["card_b"]
        assert impl.activate_ready_asset(game.state, "pete", "card_b", "asset_1") is False

        # 新一轮重置
        _emit(game, GameEvent.ROUND_BEGINS)
        assert impl.activate_ready_asset(game.state, "pete", "card_b", "asset_1") is True

    def test_ready_asset_requires_exhausted_asset_and_card_in_hand(self, game, impl):
        """目标未横置或手牌不在手中时失败。"""
        asset = _add_exhausted_asset(game)
        inv = game.state.get_investigator("pete")
        inv.hand = ["card_a"]

        # 手牌不在手中
        assert impl.activate_ready_asset(game.state, "pete", "card_z", "asset_1") is False

        # 资产未横置
        asset.exhausted = False
        assert impl.activate_ready_asset(game.state, "pete", "card_a", "asset_1") is False

    def test_elder_sign_plus_two_and_readies_duke(self, game, impl):
        """远古印记：+2，并准备杜克。"""
        duke_id = impl.setup_duke(game.state, "pete")
        duke = game.state.get_card_instance(duke_id)
        duke.exhausted = True

        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="pete", chaos_token=ChaosTokenType.ELDER_SIGN,
            amount=0,
        )
        assert ctx.amount == 2
        assert duke.exhausted is False
