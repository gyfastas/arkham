"""Tests for Marie Lambeau investigator ability and elder sign."""

import pytest

from backend.cards.mystic.marie_lambeau import MarieLambeau
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_marie")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="marie_lambeau", name="Marie Lambeau")
    g.register_card_data(inv_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)

    asset_data = make_asset_data(id="test_asset", name="Test Asset", health=2, sanity=2)
    g.register_card_data(asset_data)

    g.add_investigator("marie", inv_data, deck=["card_a"] * 10, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)
    return g


@pytest.fixture
def impl(game):
    impl = MarieLambeau("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _add_asset(game, instance_id="asset_1", doom=0, owner="marie"):
    asset = CardInstance(
        instance_id=instance_id, card_id="test_asset",
        owner_id=owner, controller_id=owner, doom=doom,
    )
    game.state.cards_in_play[instance_id] = asset
    game.state.get_investigator(owner).play_area.append(instance_id)
    return asset


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


class TestMarieLambeauExtraAction:
    def test_extra_action_with_doom_in_play(self, game, impl):
        """控制的卡牌上有毁灭标记时，回合开始获得额外行动。"""
        _add_asset(game, doom=1)
        inv = game.state.get_investigator("marie")
        inv.actions_remaining = 3

        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="marie")
        assert inv.actions_remaining == 4

    def test_no_extra_action_without_doom(self, game, impl):
        """无毁灭标记时不获得额外行动。"""
        _add_asset(game, doom=0)
        inv = game.state.get_investigator("marie")
        inv.actions_remaining = 3

        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="marie")
        assert inv.actions_remaining == 3

    def test_no_extra_action_for_other_investigators(self, game, impl):
        """其他调查员的回合不触发（即使玛丽有毁灭标记）。"""
        _add_asset(game, doom=1)
        other_data = make_investigator_data(id="other_inv", name="Other")
        game.register_card_data(other_data)
        other = game.add_investigator("other", other_data, deck=[], starting_location="test_location")
        other.actions_remaining = 3

        _emit(game, GameEvent.INVESTIGATOR_TURN_BEGINS, investigator_id="other")
        assert other.actions_remaining == 3


class TestMarieLambeauElderSign:
    def test_elder_sign_plus_one_and_pending_choice(self, game, impl):
        """远古印记：+1，并提供毁灭标记加减选择。"""
        _add_asset(game, doom=1)
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="marie", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 1
        pending = game.state.scenario.vars.get("pending_choice", {})
        assert pending.get("kind") == "marie_lambeau_doom"
        option_ids = [o["id"] for o in pending["options"]]
        assert "add:asset_1" in option_ids
        assert "remove:asset_1" in option_ids
        assert "decline" in option_ids

    def test_resolve_add_doom(self, game, impl):
        """选择增加毁灭标记。"""
        asset = _add_asset(game, doom=1)
        _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="marie", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert impl.resolve_doom_choice(game.state, "marie", "asset_1", 1)
        assert asset.doom == 2
        assert game.state.scenario.vars.get("pending_choice") is None

    def test_resolve_remove_doom(self, game, impl):
        """选择移除毁灭标记；无毁灭标记时不可移除。"""
        asset = _add_asset(game, doom=1)
        _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="marie", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert impl.resolve_doom_choice(game.state, "marie", "asset_1", -1)
        assert asset.doom == 0
        # 已为0：再次移除失败
        assert not impl.resolve_doom_choice(game.state, "marie", "asset_1", -1)
        assert asset.doom == 0

    def test_preset_choice_applied_immediately(self, game, impl):
        """scenario.vars 预设在远古印记结算时立即生效（一次性）。"""
        asset = _add_asset(game, doom=2)
        game.state.scenario.vars["marie_lambeau_doom_choice"] = {
            "instance_id": "asset_1", "delta": -1,
        }
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="marie", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 1
        assert asset.doom == 1
        # 预设已消费，不再挂起选择
        assert game.state.scenario.vars.get("pending_choice") is None
        assert "marie_lambeau_doom_choice" not in game.state.scenario.vars

    def test_no_effect_for_other_tokens(self, game, impl):
        """非远古印记不触发。"""
        _add_asset(game, doom=1)
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="marie", chaos_token=ChaosTokenType.ZERO,
        )
        assert ctx.amount == 0
        assert game.state.scenario.vars.get("pending_choice") is None
