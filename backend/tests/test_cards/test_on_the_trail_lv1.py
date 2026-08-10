"""Tests for On the Trail (Level 1). (08084)

选择其他地点的一个敌人：向其移动两次，或在你们之间最短路径上的
空地点发现1条线索。
"""

import pytest
from backend.cards.guardian.on_the_trail_lv1 import OnTheTrail
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import GameEvent, PlayerClass
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    # 线性三地点 A-B-C
    g.register_card_data(make_location_data(
        id="loc_a", name="A", connections=["loc_b"]))
    g.register_card_data(make_location_data(
        id="loc_b", name="B", connections=["loc_a", "loc_c"]))
    g.register_card_data(make_location_data(
        id="loc_c", name="C", connections=["loc_b"]))
    g.register_card_data(make_event_data(
        id="on_the_trail_lv1", name="On the Trail", cost=1,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(make_enemy_data(id="wolf", name="Wolf", fight=3, health=3))

    g.add_investigator("inv1", inv_data, starting_location="loc_a")
    g.add_location("loc_a", g.state.get_card_data("loc_a"), clues=0)
    g.add_location("loc_b", g.state.get_card_data("loc_b"), clues=1)
    g.add_location("loc_c", g.state.get_card_data("loc_c"), clues=0)
    g.card_registry.register_class(OnTheTrail)

    g.state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="wolf",
        owner_id="scenario", controller_id="scenario",
    )
    g.state.get_location("loc_c").enemies.append("enemy_1")
    return g


def _play(game, **extra):
    game.card_registry.activate_card(
        "on_the_trail_lv1", game.state.next_instance_id(), game.event_bus)
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "on_the_trail_lv1", **extra},
    )
    game.event_bus.emit(ctx)
    return ctx


class TestOnTheTrail:
    def test_move_twice_toward_enemy(self, game):
        """移动模式：沿最短路径移动2步（A→B→C）。"""
        inv = game.state.get_investigator("inv1")
        ctx = _play(game, mode="move")
        assert inv.location_id == "loc_c"
        assert ctx.extra["on_the_trail_moved"] == "loc_c"
        assert ctx.extra["on_the_trail_enemy"] == "enemy_1"

    def test_discover_clue_between(self, game):
        """线索模式：在路径之间的空地点 B 发现1条线索。"""
        inv = game.state.get_investigator("inv1")
        ctx = _play(game, mode="clue")
        assert ctx.extra["on_the_trail_clue"] == "loc_b"
        assert game.state.get_location("loc_b").clues == 0
        assert inv.clues == 1
        assert inv.location_id == "loc_a"  # 不移动

    def test_clue_mode_skips_locations_with_enemies(self, game):
        """"空地点"解释：有敌人的地点不算空（不可选）。"""
        # 把敌人挪到 B（中间点），C 放空敌人2
        game.state.get_location("loc_c").enemies.remove("enemy_1")
        game.state.get_location("loc_b").enemies.append("enemy_1")
        game.state.cards_in_play["enemy_2"] = CardInstance(
            instance_id="enemy_2", card_id="wolf",
            owner_id="scenario", controller_id="scenario",
        )
        game.state.get_location("loc_c").enemies.append("enemy_2")

        ctx = _play(game, mode="clue")
        # B 有敌人 → 不是空地点 → 路径之间没有可取的地点
        assert ctx.extra.get("on_the_trail_fizzle") is True
        assert game.state.get_location("loc_b").clues == 1

    def test_fizzle_without_enemy_elsewhere(self, game):
        """其他地点没有敌人：不结算。"""
        game.state.get_location("loc_c").enemies.remove("enemy_1")
        game.state.cards_in_play.pop("enemy_1")
        ctx = _play(game, mode="move")
        assert ctx.extra["on_the_trail_fizzle"] is True
