"""Tests for Tony Morgan investigator ability and elder sign."""

import pytest

from backend.cards.rogue.tony_morgan import TonyMorgan
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_tony")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="tony_morgan", name="Tony Morgan", combat=5)
    g.register_card_data(inv_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)

    contracts_data = make_asset_data(
        id="bounty_contracts_lv0", name="Bounty Contracts",
        uses={"bountiess": 6},  # 数据源笔误键名（见 bounty_contracts_lv0 实现）
    )
    g.register_card_data(contracts_data)

    g.add_investigator("tony", inv_data, deck=["card_a"] * 10, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)
    return g


@pytest.fixture
def impl(game):
    impl = TonyMorgan("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _add_contracts(game):
    contracts = CardInstance(
        instance_id="contracts_1", card_id="bounty_contracts_lv0",
        owner_id="tony", controller_id="tony",
        uses={"bountiess": 6},
    )
    game.state.cards_in_play["contracts_1"] = contracts
    game.state.get_investigator("tony").play_area.append("contracts_1")
    return contracts


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


class TestTonyMorganExtraAction:
    def test_extra_action_on_turn_begins(self, game, impl):
        """托尼的回合开始：获得1个额外行动。"""
        inv = game.state.get_investigator("tony")
        inv.actions_remaining = 3

        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="tony")
        assert inv.actions_remaining == 4

    def test_no_extra_action_for_other_investigators(self, game, impl):
        """其他调查员的回合不获得额外行动。"""
        other_data = make_investigator_data(id="other_inv", name="Other")
        game.register_card_data(other_data)
        other = game.add_investigator("other", other_data, deck=[], starting_location="test_location")
        other.actions_remaining = 3

        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="other")
        assert other.actions_remaining == 3


class TestTonyMorganElderSign:
    def test_elder_sign_plus_two_and_places_bounty(self, game, impl):
        """远古印记：+2，在赏金合约上放置1赏金（键名规范化为 bounties）。"""
        contracts = _add_contracts(game)
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="tony", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 2
        assert contracts.uses.get("bounties") == 7
        assert "bountiess" not in contracts.uses

    def test_elder_sign_without_contracts_in_play(self, game, impl):
        """赏金合约不在场：仍有+2，但无法放置赏金。"""
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="tony", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 2

    def test_no_effect_for_other_investigators(self, game, impl):
        """其他调查员揭示远古印记不触发。"""
        contracts = _add_contracts(game)
        other_data = make_investigator_data(id="other_inv", name="Other")
        game.register_card_data(other_data)
        game.add_investigator("other", other_data, deck=[], starting_location="test_location")

        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="other", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 0
        assert contracts.uses.get("bountiess") == 6
