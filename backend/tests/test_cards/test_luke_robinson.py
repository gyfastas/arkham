"""Tests for Luke Robinson investigator ability and elder sign."""

import pytest

from backend.cards.mystic.luke_robinson import LukeRobinson
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_luke")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="luke_robinson", name="Luke Robinson")
    g.register_card_data(inv_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)

    gate_box_data = make_asset_data(
        id="gate_box_lv0", name="Gate Box", uses={"chargess": 3},  # 数据源笔误键名
    )
    g.register_card_data(gate_box_data)

    g.add_investigator("luke", inv_data, deck=["card_a"] * 10, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)
    return g


@pytest.fixture
def impl(game):
    impl = LukeRobinson("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


def _gate_box(game):
    inv = game.state.get_investigator("luke")
    for inst_id in inv.play_area:
        inst = game.state.get_card_instance(inst_id)
        if inst is not None and inst.card_id == "gate_box_lv0":
            return inst
    return None


class TestLukeRobinsonGateBoxSetup:
    def test_setup_gate_box_places_it_in_play(self, game, impl):
        """setup_gate_box()：门之匣入场并带上初始充能（幂等）。"""
        inst_id = impl.setup_gate_box(game.state, "luke")
        assert inst_id is not None
        gate_box = _gate_box(game)
        assert gate_box is not None
        assert gate_box.uses.get("chargess") == 3

        # 幂等：再次调用不重复入场
        assert impl.setup_gate_box(game.state, "luke") == inst_id
        inv = game.state.get_investigator("luke")
        assert len(inv.play_area) == 1

    def test_round_begins_fallback_places_gate_box(self, game, impl):
        """未显式 setup 时，第一轮开始兜底让门之匣入场。"""
        assert _gate_box(game) is None
        _emit(game, GameEvent.ROUND_BEGINS)
        assert _gate_box(game) is not None

    def test_no_setup_for_other_investigators(self, game, impl):
        """其他调查员不会获得门之匣。"""
        other_data = make_investigator_data(id="other_inv", name="Other")
        game.register_card_data(other_data)
        other = game.add_investigator("other", other_data, deck=[], starting_location="test_location")

        _emit(game, GameEvent.ROUND_BEGINS)
        assert other.play_area == []
        # 卢克的门之匣仍正常入场
        assert _gate_box(game) is not None


class TestLukeRobinsonElderSign:
    def test_elder_sign_plus_one_and_adds_charge(self, game, impl):
        """远古印记：+1，在门之匣上放置1充能。"""
        gate_box = game.state.get_card_instance(impl.setup_gate_box(game.state, "luke"))

        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="luke", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 1
        assert gate_box.uses.get("chargess") == 4

    def test_elder_sign_without_gate_box(self, game, impl):
        """门之匣不在场：仍有+1，跳过放置充能。"""
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="luke", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 1

    def test_no_effect_for_other_investigators(self, game, impl):
        """其他调查员揭示远古印记不触发。"""
        gate_box = game.state.get_card_instance(impl.setup_gate_box(game.state, "luke"))
        other_data = make_investigator_data(id="other_inv", name="Other")
        game.register_card_data(other_data)
        game.add_investigator("other", other_data, deck=[], starting_location="test_location")

        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="other", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 0
        assert gate_box.uses.get("chargess") == 3
