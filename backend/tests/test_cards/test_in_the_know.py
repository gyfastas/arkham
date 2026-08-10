"""Tests for In the Know (Level 1).

官方：使用(3秘密)。[行动]花费1秘密：调查。调查场上任意1个已揭示地点，
视为你身处该地点。
"""

import pytest

from backend.cards.seeker.in_the_know_lv1 import InTheKnow
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def setup():
    g = Game("test_in_the_know")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(intellect=4)
    g.register_card_data(inv_data)
    loc_a = make_location_data(id="loc_a", shroud=2, clue_value=1,
                               connections=["loc_b"])
    loc_b = make_location_data(id="loc_b", shroud=3, clue_value=2,
                               connections=["loc_a"])
    for loc in (loc_a, loc_b):
        g.register_card_data(loc)
    g.add_investigator("player", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_a, clues=1)
    g.add_location("loc_b", loc_b, clues=2)
    g.state.get_location("loc_a").revealed = True
    g.state.get_location("loc_b").revealed = True

    g.register_card_data(make_asset_data(
        id="in_the_know_lv1", name="In the Know", cost=3,
        uses={"secrets": 3}, traits=["talent"],
    ))
    inst = CardInstance(
        instance_id="inst_itk", card_id="in_the_know_lv1",
        owner_id="player", controller_id="player",
    )
    inst.uses = {"secrets": 3}
    g.state.cards_in_play["inst_itk"] = inst
    g.state.get_investigator("player").play_area.append("inst_itk")

    impl = InTheKnow("inst_itk")
    impl.register(g.event_bus, "inst_itk")
    impl.bind_chaos_bag(g.chaos_bag)
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]
    return g, impl


class TestInTheKnow:
    def test_remote_investigate_success(self, setup):
        """指定远程地点：按其隐蔽值检定，成功从该地点发现线索。"""
        game, impl = setup
        inv = game.state.get_investigator("player")
        loc_a = game.state.get_location("loc_a")
        loc_b = game.state.get_location("loc_b")

        assert impl.activate(game.state, "player",
                             target_location_id="loc_b") is True
        assert inv.clues == 1
        assert loc_b.clues == 1
        assert loc_a.clues == 1  # 本地点线索不动
        inst = game.state.get_card_instance("inst_itk")
        assert inst.uses["secrets"] == 2

    def test_auto_selects_revealed_location_with_clues(self, setup):
        """缺省目标：自动选第一个已揭示且有线索的其他地点（loc_b）。"""
        game, impl = setup
        loc_b = game.state.get_location("loc_b")
        assert impl.activate(game.state, "player") is True
        assert loc_b.clues == 1  # 远程地点线索被发现

    def test_failure_no_clue(self, setup):
        game, impl = setup
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_4]  # 4-4=0 < 3
        inv = game.state.get_investigator("player")
        loc_b = game.state.get_location("loc_b")
        assert impl.activate(game.state, "player",
                             target_location_id="loc_b") is True
        assert inv.clues == 0
        assert loc_b.clues == 2

    def test_no_secrets_cannot_activate(self, setup):
        game, impl = setup
        inst = game.state.get_card_instance("inst_itk")
        inst.uses["secrets"] = 0
        assert impl.activate(game.state, "player") is False
