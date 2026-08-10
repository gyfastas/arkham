"""Tests for Hallow (Level 3). (07301)

额外费用：10个祝福标记返回供应堆；移除场上1点毁灭。
"""

import pytest
from backend.cards.guardian.hallow_lv3 import Hallow
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent, PlayerClass
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_event_data(
        id="hallow_lv3", name="Hallow", cost=3,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=0)
    g.card_registry.register_class(Hallow)
    return g


def _play(game):
    impl = game.card_registry.activate_card(
        "hallow_lv3", game.state.next_instance_id(), game.event_bus,
        chaos_bag=game.chaos_bag)
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1", extra={"card_id": "hallow_lv3"},
    )
    game.event_bus.emit(ctx)
    return ctx


class TestHallow:
    def test_returns_10_bless_and_removes_doom(self, game):
        """10个祝福返回供应堆；自动移除剧情上的1点毁灭。"""
        for _ in range(10):
            game.chaos_bag.add_token(ChaosTokenType.BLESS)
        game.state.scenario.doom_on_agenda = 2

        ctx = _play(game)

        assert game.chaos_bag.tokens.count(ChaosTokenType.BLESS) == 0
        assert game.state.scenario.doom_on_agenda == 1
        assert ctx.extra["hallow_doom_removed"] == "剧情"

    def test_uses_sealed_bless_to_pay(self, game):
        """袋中不足时从封印的祝福中补足10个。"""
        for _ in range(7):
            game.chaos_bag.add_token(ChaosTokenType.BLESS)
        for _ in range(3):
            game.chaos_bag.add_token(ChaosTokenType.BLESS)
            game.chaos_bag.seal_token(ChaosTokenType.BLESS)
        game.state.scenario.doom_on_agenda = 1

        _play(game)

        assert game.chaos_bag.tokens.count(ChaosTokenType.BLESS) == 0
        assert game.chaos_bag.sealed.count(ChaosTokenType.BLESS) == 0
        assert game.state.scenario.doom_on_agenda == 0

    def test_fizzle_without_10_bless(self, game):
        """合计不足10个祝福：效果不结算。"""
        for _ in range(9):
            game.chaos_bag.add_token(ChaosTokenType.BLESS)
        game.state.scenario.doom_on_agenda = 2

        ctx = _play(game)

        assert ctx.extra["hallow_fizzle"] is True
        assert game.chaos_bag.tokens.count(ChaosTokenType.BLESS) == 9
        assert game.state.scenario.doom_on_agenda == 2

    def test_remove_doom_from_card(self, game):
        """剧情无毁灭时：移除场上卡牌的毁灭。"""
        from backend.models.state import CardInstance
        game.state.cards_in_play["cult"] = CardInstance(
            instance_id="cult", card_id="test_location",
            owner_id="scenario", controller_id="scenario",
        )
        game.state.cards_in_play["cult"].doom = 1
        for _ in range(10):
            game.chaos_bag.add_token(ChaosTokenType.BLESS)

        ctx = _play(game)
        assert game.state.cards_in_play["cult"].doom == 0
