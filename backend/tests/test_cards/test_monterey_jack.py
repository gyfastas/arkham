"""Tests for Monterey Jack investigator ability."""

import pytest
from backend.cards.rogue.monterey_jack import MontereyJack
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent
from backend.tests.conftest import (
    make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_monterey")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="monterey_jack", name="Monterey Jack")
    g.register_card_data(inv_data)

    # 链式地点：loc_a - loc_b - loc_c
    for loc_id, conns in [("loc_a", ["loc_b"]), ("loc_b", ["loc_a", "loc_c"]),
                          ("loc_c", ["loc_b"])]:
        loc_data = make_location_data(id=loc_id, connections=conns)
        g.register_card_data(loc_data)
        g.add_location(loc_id, loc_data, clues=1)

    deck = ["card_a", "card_b", "card_c", "card_d", "card_e"] * 3
    g.add_investigator("jack", inv_data, deck=deck, starting_location="loc_a")

    return g


@pytest.fixture
def impl(game):
    impl = MontereyJack("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


def _start_round_at(game, location_id):
    inv = game.state.get_investigator("jack")
    inv.location_id = location_id
    _emit(game, GameEvent.ROUND_BEGINS)


class TestMontereyTurnEnd:
    def test_no_movement_no_reward(self, game, impl):
        """本轮未移动：回合结束无奖励。"""
        _start_round_at(game, "loc_a")
        _emit(game, GameEvent.INVESTIGATOR_TURN_ENDS, investigator_id="jack")
        assert game.state.scenario.vars.get("pending_choice") is None

    def test_one_away_offers_choice(self, game, impl):
        """相隔1个地点：二选一（资源/抽牌）。"""
        inv = game.state.get_investigator("jack")
        _start_round_at(game, "loc_a")
        inv.location_id = "loc_b"
        _emit(game, GameEvent.INVESTIGATOR_TURN_ENDS, investigator_id="jack")

        pending = game.state.scenario.vars.get("pending_choice")
        assert pending is not None
        assert pending["kind"] == "monterey_jack_turn_end"
        assert [o["id"] for o in pending["options"]] == ["resource", "card"]

        resources_before = inv.resources
        assert impl.resolve_turn_end(game.state, "jack", "resource") is True
        assert inv.resources == resources_before + 1
        assert game.state.scenario.vars.get("pending_choice") is None

    def test_one_away_choose_card(self, game, impl):
        """二选一选抽牌。"""
        inv = game.state.get_investigator("jack")
        _start_round_at(game, "loc_a")
        inv.location_id = "loc_b"
        _emit(game, GameEvent.INVESTIGATOR_TURN_ENDS, investigator_id="jack")

        hand_before = len(inv.hand)
        deck_before = len(inv.deck)
        assert impl.resolve_turn_end(game.state, "jack", "card") is True
        assert len(inv.hand) == hand_before + 1
        assert len(inv.deck) == deck_before - 1

    def test_two_away_grants_both(self, game, impl):
        """相隔2+地点：自动执行两项（无二选一）。"""
        inv = game.state.get_investigator("jack")
        _start_round_at(game, "loc_a")
        inv.location_id = "loc_c"
        resources_before = inv.resources
        hand_before = len(inv.hand)
        _emit(game, GameEvent.INVESTIGATOR_TURN_ENDS, investigator_id="jack")

        assert inv.resources == resources_before + 1
        assert len(inv.hand) == hand_before + 1
        assert game.state.scenario.vars.get("pending_choice") is None

    def test_other_investigator_turn_end_not_triggered(self, game, impl):
        """其他调查员回合结束不触发。"""
        other_data = make_investigator_data(id="other_inv", name="Other")
        game.register_card_data(other_data)
        game.add_investigator("other", other_data, deck=[], starting_location="loc_a")
        _start_round_at(game, "loc_a")
        game.state.get_investigator("other").location_id = "loc_b"
        _emit(game, GameEvent.INVESTIGATOR_TURN_ENDS, investigator_id="other")
        assert game.state.scenario.vars.get("pending_choice") is None


class TestMontereyElderSign:
    def test_elder_sign_plus_one_no_movement(self, game, impl):
        """未移动：仅 +1，无奖励。"""
        inv = game.state.get_investigator("jack")
        _start_round_at(game, "loc_a")
        resources_before = inv.resources
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="jack", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 1
        assert inv.resources == resources_before

    def test_elder_sign_reward_default_resource(self, game, impl):
        """移动过：+1 并获得1资源（默认二选一）。"""
        inv = game.state.get_investigator("jack")
        _start_round_at(game, "loc_a")
        inv.location_id = "loc_b"
        resources_before = inv.resources
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="jack", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 1
        assert inv.resources == resources_before + 1

    def test_elder_sign_reward_choose_card(self, game, impl):
        """预设抽牌：+1 并抽1张牌。"""
        inv = game.state.get_investigator("jack")
        _start_round_at(game, "loc_a")
        inv.location_id = "loc_c"  # 相隔2地点，远古印记同样只给一项
        assert impl.choose_elder_sign_choice(game.state, "jack", "card") is True

        hand_before = len(inv.hand)
        resources_before = inv.resources
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="jack", chaos_token=ChaosTokenType.ELDER_SIGN,
        )
        assert ctx.amount == 1
        assert len(inv.hand) == hand_before + 1
        assert inv.resources == resources_before

    def test_choose_choice_validates(self, game, impl):
        assert impl.choose_elder_sign_choice(game.state, "jack", "bogus") is False
