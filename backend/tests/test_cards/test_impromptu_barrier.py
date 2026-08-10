"""Tests for Impromptu Barrier (Level 0)."""

import pytest
from backend.cards.survivor.impromptu_barrier_lv0 import ImpromptuBarrier
from backend.models.enums import (
    Action, ChaosTokenType, GameEvent, PlayerClass,
)
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)
from backend.engine.event_bus import EventContext
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(agility=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="impromptu_barrier_lv0", name="Impromptu Barrier", cost=1,
        card_class=PlayerClass.SURVIVOR))
    g.register_card_data(make_enemy_data(
        id="enemy_a", name="Enemy A", fight=3, health=5, evade=4))
    g.register_card_data(make_enemy_data(
        id="enemy_b", name="Enemy B", fight=3, health=5, evade=2))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(ImpromptuBarrier)
    return g


def _spawn(game, iid, card_id, engaged=True):
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    if engaged:
        game.state.get_investigator("inv1").threat_area.append(iid)
    else:
        game.state.get_location("test_location").enemies.append(iid)
    return game.state.cards_in_play[iid]


def _play_from_discard(game, token):
    """模拟会话层从弃牌堆打出（引擎缺口：_play 要求手牌）。"""
    impl = ImpromptuBarrier(f"impl_barrier_{token.value}")
    impl.register(game.event_bus, impl.instance_id)
    impl.bind_chaos_bag(game.chaos_bag)
    game.chaos_bag.tokens = [token]
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "impromptu_barrier_lv0",
               "played_from_discard": True},
    )
    game.event_bus.emit(ctx)
    return ctx, impl


class TestImpromptuBarrier:
    def test_card_registered(self, game):
        assert "impromptu_barrier_lv0" in game.card_registry.registered_cards

    def test_evade_with_minus_1_evade(self, game):
        """躲避检定目标 -1 躲避值（敏捷3对躲避4-1=3）。"""
        enemy = _spawn(game, "e1", "enemy_a")  # 躲避4
        inv = game.state.get_investigator("inv1")
        inv.hand = ["impromptu_barrier_lv0"]
        inv.resources = 3
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        assert game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="impromptu_barrier_lv0") is True

        assert enemy.exhausted is True
        assert "e1" not in inv.threat_area

    def test_from_discard_evades_additional_enemy(self, game):
        """弃牌堆打出：追加躲避同地点躲避值≤超出量的敌人。"""
        e1 = _spawn(game, "e1", "enemy_b")                # 躲避2 → 难度1
        e2 = _spawn(game, "e2", "enemy_b", engaged=False)  # 躲避2
        inv = game.state.get_investigator("inv1")

        # 敏捷3+1=4 vs 难度1：超出3 ≥ e2躲避值2 → 追加躲避
        ctx, _impl = _play_from_discard(game, ChaosTokenType.PLUS_1)

        assert ctx.extra["impromptu_barrier_success"] is True
        assert e1.exhausted is True
        assert "e1" not in inv.threat_area
        assert e2.exhausted is True
        assert ctx.extra["impromptu_barrier_second"] == "e2"

    def test_from_discard_margin_too_small_no_additional(self, game):
        """超出量不足时不追加躲避。"""
        e1 = _spawn(game, "e1", "enemy_a")                # 躲避4 → 难度3
        e2 = _spawn(game, "e2", "enemy_b", engaged=False)  # 躲避2
        inv = game.state.get_investigator("inv1")

        # 敏捷3+1=4 vs 难度3：超出1 < e2躲避值2
        ctx, _impl = _play_from_discard(game, ChaosTokenType.PLUS_1)

        assert e1.exhausted is True
        assert e2.exhausted is False
        assert "impromptu_barrier_second" not in ctx.extra

    def test_from_discard_shuffles_into_deck_after_resolution(self, game):
        """弃牌堆打出结算后洗回牌库（而非留在弃牌堆）。"""
        _spawn(game, "e1", "enemy_b")
        inv = game.state.get_investigator("inv1")

        ctx, _impl = _play_from_discard(game, ChaosTokenType.PLUS_1)
        # 引擎/会话在结算后将事件置入弃牌堆
        inv.discard.append("impromptu_barrier_lv0")

        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.ROUND_ENDS))

        assert "impromptu_barrier_lv0" in inv.deck
        assert "impromptu_barrier_lv0" not in inv.discard
