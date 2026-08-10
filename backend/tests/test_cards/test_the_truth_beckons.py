"""Tests for The Truth Beckons (Level 0).

官方：只能在你未与敌人交战时打出。移动。选择一个未揭示地点，沿最短
路径一次一个地点移动直到进入该地点。若翻开地点/与敌人交战/移动被
阻挡则结束效果。
"""

import pytest

from backend.cards.seeker.the_truth_beckons_lv0 import TheTruthBeckons
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import GameEvent
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_truth_beckons")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    # 地图：a - b - c(未揭示) - d(未揭示)
    locs = {
        "loc_a": make_location_data(id="loc_a", connections=["loc_b"]),
        "loc_b": make_location_data(id="loc_b", connections=["loc_a", "loc_c"]),
        "loc_c": make_location_data(id="loc_c", connections=["loc_b", "loc_d"]),
        "loc_d": make_location_data(id="loc_d", connections=["loc_c"]),
    }
    for loc in locs.values():
        g.register_card_data(loc)
    g.add_investigator("player", inv_data, starting_location="loc_a")
    for loc_id, loc in locs.items():
        g.add_location(loc_id, loc, clues=0)
    # a、b 已揭示；c、d 未揭示
    g.state.get_location("loc_a").revealed = True
    g.state.get_location("loc_b").revealed = True

    g.card_registry.register_class(TheTruthBeckons)
    g.card_registry.activate_card(
        "the_truth_beckons_lv0", "impl_ttb", g.event_bus,
        chaos_bag=g.chaos_bag)
    return g


def _play(game, **extra):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id="player",
        extra={"card_id": "the_truth_beckons_lv0", **extra},
    )
    game.event_bus.emit(ctx)
    return ctx


class TestTheTruthBeckons:
    def test_moves_along_shortest_path_to_target(self, game):
        """指定未揭示的 d：沿 a→b→c→d 移动；进入未揭示的 c 即翻开并停止。"""
        inv = game.state.get_investigator("player")
        ctx = _play(game, target_location_id="loc_d")
        # c 是路径上第一个未揭示地点：进入并翻开，效果结束
        assert inv.location_id == "loc_c"
        assert game.state.get_location("loc_c").revealed is True
        assert ctx.extra.get("truth_beckons_moved") == "loc_c"

    def test_auto_targets_nearest_unrevealed(self, game):
        """缺省目标：最近的未揭示地点（c）。"""
        inv = game.state.get_investigator("player")
        ctx = _play(game)
        assert inv.location_id == "loc_c"
        assert ctx.extra.get("truth_beckons_moved") == "loc_c"

    def test_engaged_cannot_play(self, game):
        """与敌人交战时不能打出：效果不生效。"""
        inv = game.state.get_investigator("player")
        game.register_card_data(make_enemy_data())
        enemy = CardInstance(
            instance_id="enemy_1", card_id="test_enemy",
            owner_id="scenario", controller_id="scenario",
        )
        game.state.cards_in_play["enemy_1"] = enemy
        inv.threat_area.append("enemy_1")
        ctx = _play(game)
        assert ctx.extra.get("truth_beckons_failed") == "engaged"
        assert inv.location_id == "loc_a"
