"""Tests for Vantage Point (Level 0).

官方：快速。在一个地点入场或被翻开后打出。该地点-1隐藏值直到当前
调查员回合结束。你可以将其它任何地点上的1个线索移动到该地点上。
"""

import pytest

from backend.cards.seeker.vantage_point_lv0 import VantagePoint
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, GameEvent
from backend.tests.conftest import (
    make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_vantage_point")
    g.chaos_bag.seed(42)
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]

    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)
    loc_a = make_location_data(id="loc_a", shroud=3, connections=["loc_b"])
    loc_b = make_location_data(id="loc_b", shroud=2, connections=["loc_a"])
    g.register_card_data(loc_a)
    g.register_card_data(loc_b)
    g.add_investigator("player", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_a, clues=1)
    g.add_location("loc_b", loc_b, clues=2)

    g.card_registry.register_class(VantagePoint)
    g.card_registry.activate_card(
        "vantage_point_lv0", "impl_vp", g.event_bus,
        chaos_bag=g.chaos_bag)
    return g


def _play(game, **extra):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id="player",
        extra={"card_id": "vantage_point_lv0", **extra},
    )
    game.event_bus.emit(ctx)
    return ctx


class TestVantagePoint:
    def test_shroud_reduction_and_clue_move(self, game):
        """目标地点-1隐藏值（难度3→2）；从其它地点移1个线索过来。"""
        inv = game.state.get_investigator("player")
        loc_a = game.state.get_location("loc_a")
        loc_b = game.state.get_location("loc_b")
        ctx = _play(game, location_id="loc_a")
        assert ctx.extra.get("vantage_point_location") == "loc_a"
        assert ctx.extra.get("vantage_point_moved_from") == "loc_b"
        assert loc_a.clues == 2
        assert loc_b.clues == 1

        # 调查 loc_a（隐藏值3）：难度降为2，智力3成功
        game.action_resolver.perform_action("player", Action.INVESTIGATE)
        assert inv.clues == 1  # 调查成功发现1个线索
        assert loc_a.clues == 1

    def test_expires_at_turn_end(self, game):
        """当前调查员回合结束后：难度不再降低。"""
        _play(game, location_id="loc_a")
        game.event_bus.emit(EventContext(
            game_state=game.state, event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="player"))
        # 直接发起调查检定：难度恢复为3，智力3仍成功但需验证难度未被降
        result_holder = {}
        def _capture(ctx):
            result_holder["difficulty"] = ctx.difficulty
        game.event_bus.register(
            GameEvent.SKILL_TEST_BEGINS, _capture,
        )
        game.action_resolver.perform_action("player", Action.INVESTIGATE)
        assert result_holder["difficulty"] == 3
