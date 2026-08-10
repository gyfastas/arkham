"""Tests for Righteous Hunt (Level 1). (07109)

交战：移动到2连接地点内的敌人处并交战，按其恐惧值加祝福标记入袋。
"""

import pytest

from backend.cards.guardian.righteous_hunt_lv1 import RighteousHunt
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, PlayerClass
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    """A—B—C；敌人（恐惧2）在 C。"""
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    for loc_id, conns in (
        ("loc_a", ["loc_b"]),
        ("loc_b", ["loc_a", "loc_c"]),
        ("loc_c", ["loc_b"]),
    ):
        loc = make_location_data(id=loc_id, connections=conns)
        g.register_card_data(loc)
        g.add_location(loc_id, loc)

    g.register_card_data(make_event_data(
        id="righteous_hunt_lv1", name="Righteous Hunt", cost=1,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(make_enemy_data(id="cultist", health=3, horror=2))

    g.add_investigator("inv1", inv_data, starting_location="loc_a")
    g.card_registry.register_class(RighteousHunt)

    enemy = CardInstance(
        instance_id="enemy_1", card_id="cultist",
        owner_id="scenario", controller_id="scenario",
    )
    g.state.cards_in_play["enemy_1"] = enemy
    g.state.locations["loc_c"].enemies.append("enemy_1")

    inv = g.state.get_investigator("inv1")
    inv.hand.append("righteous_hunt_lv1")
    inv.actions_remaining = 3
    return g


def _bless_count(game):
    return sum(1 for t in game.chaos_bag.tokens if t == ChaosTokenType.BLESS)


class TestRighteousHunt:
    def test_move_engage_and_bless(self, game):
        """打出后：移动到敌人地点并交战，袋中加入2个祝福标记。"""
        inv = game.state.get_investigator("inv1")
        before = _bless_count(game)

        ok = game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="righteous_hunt_lv1",
        )
        assert ok is True
        assert inv.location_id == "loc_c"
        assert "enemy_1" in inv.threat_area
        assert "enemy_1" not in game.state.locations["loc_c"].enemies
        assert _bless_count(game) == before + 2

    def test_out_of_range_fizzles(self, game):
        """敌人距离3个地点（超出2）：不移动不交战。"""
        loc_d = make_location_data(id="loc_d", connections=["loc_c"])
        game.register_card_data(loc_d)
        game.add_location("loc_d", loc_d)
        game.state.locations["loc_c"].enemies.remove("enemy_1")
        game.state.locations["loc_d"].enemies.append("enemy_1")
        inv = game.state.get_investigator("inv1")
        before = _bless_count(game)

        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="righteous_hunt_lv1",
        )
        assert inv.location_id == "loc_a"
        assert "enemy_1" not in inv.threat_area
        assert _bless_count(game) == before
