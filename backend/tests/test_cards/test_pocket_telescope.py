"""Tests for Pocket Telescope (Level 0).

官方：[快速]消耗：查看一个连接的未揭示地点的已揭示面。
[行动]：调查。调查一个连接的已揭示地点，如同你在那里。
"""

import pytest

from backend.cards.seeker.pocket_telescope_lv0 import PocketTelescope
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_pocket_telescope")
    g.chaos_bag.seed(42)
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]

    inv_data = make_investigator_data(intellect=4)
    g.register_card_data(inv_data)
    loc_a = make_location_data(id="loc_a", shroud=2, connections=["loc_b", "loc_c"])
    loc_b = make_location_data(id="loc_b", shroud=3, connections=["loc_a"])
    loc_c = make_location_data(id="loc_c", shroud=5, connections=["loc_a"])
    for loc in (loc_a, loc_b, loc_c):
        g.register_card_data(loc)
    g.add_investigator("player", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_a, clues=0)
    g.add_location("loc_b", loc_b, clues=2)
    g.add_location("loc_c", loc_c, clues=1)
    g.state.get_location("loc_a").revealed = True
    g.state.get_location("loc_b").revealed = True
    # loc_c 未揭示

    g.register_card_data(make_asset_data(
        id="pocket_telescope_lv0", name="Pocket Telescope", cost=2))
    inst = CardInstance(
        instance_id="inst_pt", card_id="pocket_telescope_lv0",
        owner_id="player", controller_id="player",
    )
    g.state.cards_in_play["inst_pt"] = inst
    g.state.get_investigator("player").play_area.append("inst_pt")

    impl = PocketTelescope("inst_pt")
    impl.register(g.event_bus, "inst_pt")
    impl.bind_chaos_bag(g.chaos_bag)
    return g, impl


class TestPocketTelescope:
    def test_peek_unrevealed_connecting_location(self, game):
        """[快速]查看连接未揭示地点：消耗并记录，地点不翻开。"""
        g, impl = game
        inst = g.state.get_card_instance("inst_pt")
        peeked = impl.peek(g.state, "player")
        assert peeked == "loc_c"
        assert inst.exhausted is True
        assert g.state.get_location("loc_c").revealed is False
        peeked_log = g.state.scenario.vars.get("peeked_locations")
        assert "loc_c" in peeked_log.get("player", [])

    def test_remote_investigate_connecting_revealed(self, game):
        """[行动]调查连接的已揭示地点（智力4对隐藏值3成功），从该地点发现线索。"""
        g, impl = game
        inv = g.state.get_investigator("player")
        loc_b = g.state.get_location("loc_b")
        assert impl.investigate_remote(g.state, "player", "loc_b") is True
        assert loc_b.clues == 1
        assert inv.clues == 1
        # 调查者没有移动
        assert inv.location_id == "loc_a"

    def test_remote_investigate_rejects_unrevealed(self, game):
        """未揭示地点不是远程调查的合法目标。"""
        g, impl = game
        assert impl.investigate_remote(g.state, "player", "loc_c") is False

    def test_peek_rejects_revealed(self, game):
        """已揭示地点不是查看的合法目标。"""
        g, impl = game
        assert impl.peek(g.state, "player", "loc_b") is None
