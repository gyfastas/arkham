"""Tests for Cherished Keepsake (Level 0).

官方卡面无能力文本：sanity 2 承恐资产。实现为登记在册的 inert
（同 leather_coat_lv0）；行为测试验证其承恐容量经引擎分配通道生效。
"""

import pytest
from backend.cards.survivor.cherished_keepsake_lv0 import CherishedKeepsake
from backend.models.enums import PlayerClass, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="cherished_keepsake_lv0", name="Cherished Keepsake", cost=0,
        card_class=PlayerClass.SURVIVOR, slots=[SlotType.ACCESSORY],
        sanity=2, traits=["item", "charm"],
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(CherishedKeepsake)
    return g


def _put_in_play(game):
    inv = game.state.get_investigator("inv1")
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id="cherished_keepsake_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    inv.play_area.append(iid)
    return iid


class TestCherishedKeepsake:
    def test_card_registered(self, game):
        assert "cherished_keepsake_lv0" in game.card_registry.registered_cards

    def test_soaks_two_horror(self, game):
        """2点理智承恐容量：承1点留场；承满2点被击败，余下恐惧给调查员。"""
        iid = _put_in_play(game)
        inv = game.state.get_investigator("inv1")

        soak = game.damage_engine.get_ally_soak_targets("inv1")
        entry = next(t for t in soak if t["instance_id"] == iid)
        assert entry["remaining_sanity"] == 2

        # 承1点：留场，调查员承受余下1点
        game.damage_engine.deal_damage("inv1", horror=2,
                                       horror_assignment={iid: 1})
        inst = game.state.get_card_instance(iid)
        assert inst.horror == 1
        assert inv.horror == 1
        assert iid in inv.play_area

    def test_defeated_when_horror_full(self, game):
        """承满2恐惧后被击败离场，进入弃牌堆。"""
        iid = _put_in_play(game)
        inv = game.state.get_investigator("inv1")

        game.damage_engine.deal_damage("inv1", horror=2,
                                       horror_assignment={iid: 2})
        assert game.state.get_card_instance(iid) is None
        assert iid not in inv.play_area
        assert "cherished_keepsake_lv0" in inv.discard
