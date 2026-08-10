"""Tests for Segment of Onyx (Level 1).

官方：多重。快速。[快速]如果你场上有3张一瓣缟玛瑙：将它们放在一边
（场外），在你的绑定卡牌中查找并将皇后的挂坠放置入场。
"""

import pytest

from backend.cards.seeker.segment_of_onyx_lv1 import SegmentOfOnyx
from backend.engine.game import Game
from backend.models.enums import SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_segment_of_onyx")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a")
    g.register_card_data(loc_data)
    g.add_investigator("player", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_data, clues=0)

    g.register_card_data(make_asset_data(
        id="segment_of_onyx_lv1", name="Segment of Onyx", cost=1,
        traits=["item", "relic", "occult"]))
    g.register_card_data(make_asset_data(
        id="pendant_of_the_queen_lv0", name="Pendant of the Queen",
        cost=None, traits=["item", "relic"], slots=[SlotType.ACCESSORY],
        uses={"chargess": 3},  # 数据笔误键名
    ))

    # 场上3张一瓣缟玛瑙（无槽位）
    impls = []
    for i in range(3):
        iid = f"inst_seg_{i}"
        inst = CardInstance(
            instance_id=iid, card_id="segment_of_onyx_lv1",
            owner_id="player", controller_id="player",
        )
        g.state.cards_in_play[iid] = inst
        g.state.get_investigator("player").play_area.append(iid)
        impl = SegmentOfOnyx(iid)
        impl.register(g.event_bus, iid)
        impls.append(impl)
    return g, impls[0]


class TestSegmentOfOnyx:
    def test_assemble_three_summons_pendant(self, game):
        """集齐3张：全部放场外，皇后的挂坠入场（3充能，占饰品槽）。"""
        g, impl = game
        inv = g.state.get_investigator("player")
        assert impl.activate(g.state, "player") is True

        # 3张缟玛瑙离场且不在弃牌堆（场外）
        assert inv.play_area != ["inst_seg_0", "inst_seg_1", "inst_seg_2"]
        assert not any(iid.startswith("inst_seg_") for iid in inv.play_area)
        assert "segment_of_onyx_lv1" not in inv.discard
        set_aside = g.state.scenario.vars.get("set_aside_out_of_play", [])
        assert set_aside.count("segment_of_onyx_lv1") == 3

        # 皇后的挂坠入场
        pendant = [
            g.state.get_card_instance(iid) for iid in inv.play_area
            if (ci := g.state.get_card_instance(iid)) is not None
            and ci.card_id == "pendant_of_the_queen_lv0"
        ]
        assert len(pendant) == 1
        assert pendant[0].uses.get("charges") == 3  # 笔误键名已规范化

    def test_two_segments_not_enough(self, game):
        """只有2张：不能发动。"""
        g, impl = game
        inv = g.state.get_investigator("player")
        # 移除一张
        inv.play_area.remove("inst_seg_2")
        g.state.cards_in_play.pop("inst_seg_2")
        assert impl.activate(g.state, "player") is False
