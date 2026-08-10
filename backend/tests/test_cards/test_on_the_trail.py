"""Tests for On the Trail (Level 3). (08085)

选择其他地点的一名敌人，朝它移动2次，每个进入的地点发现1线索。
"""

import pytest

from backend.cards.guardian.on_the_trail_lv3 import OnTheTrail
from backend.engine.game import Game
from backend.models.enums import Action, CardType, PlayerClass
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    """A—B—C 直线三地点；敌人 spinner 在 C。"""
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    for loc_id, conns, clues in (
        ("loc_a", ["loc_b"], 0),
        ("loc_b", ["loc_a", "loc_c"], 1),
        ("loc_c", ["loc_b"], 1),
    ):
        loc = make_location_data(id=loc_id, connections=conns, clue_value=clues)
        g.register_card_data(loc)
        g.add_location(loc_id, loc, clues=clues)

    g.register_card_data(make_event_data(
        id="on_the_trail_lv3", name="On the Trail", cost=1,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(make_enemy_data(id="ghoul", health=3))

    g.add_investigator("inv1", inv_data, starting_location="loc_a")
    g.card_registry.register_class(OnTheTrail)

    enemy = CardInstance(
        instance_id="enemy_1", card_id="ghoul",
        owner_id="scenario", controller_id="scenario",
    )
    g.state.cards_in_play["enemy_1"] = enemy
    g.state.locations["loc_c"].enemies.append("enemy_1")

    inv = g.state.get_investigator("inv1")
    inv.hand.append("on_the_trail_lv3")
    inv.actions_remaining = 3
    return g


class TestOnTheTrail:
    def test_move_twice_and_discover(self, game):
        """打出后：沿最短路径移动2步（A→B→C），B、C各发现1线索。"""
        inv = game.state.get_investigator("inv1")
        ok = game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="on_the_trail_lv3",
        )
        assert ok is True
        assert inv.location_id == "loc_c"
        assert inv.clues == 2
        assert game.state.locations["loc_b"].clues == 0
        assert game.state.locations["loc_c"].clues == 0

    def test_no_enemy_fizzles(self, game):
        """其他地点没有敌人：不移动、不发现线索。"""
        loc = game.state.locations["loc_c"]
        loc.enemies.remove("enemy_1")
        game.state.cards_in_play.pop("enemy_1")
        inv = game.state.get_investigator("inv1")

        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="on_the_trail_lv3",
        )
        assert inv.location_id == "loc_a"
        assert inv.clues == 0
