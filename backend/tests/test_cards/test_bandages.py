"""Tests for Bandages (Level 0)."""

import pytest

from backend.cards.survivor.bandages_lv0 import Bandages
from backend.engine.game import Game
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data(health=9)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    # 数据文件键名为 "suppliess"（笔误），实现两种键名兼容
    g.register_card_data(make_asset_data(
        id="bandages_lv0", name="Bandages", cost=2,
        traits=["item"], uses={"suppliess": 3}))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(Bandages)
    return g


def _play_bandages(game):
    from backend.models.enums import Action
    inv = game.state.get_investigator("inv1")
    inv.resources = 5
    inv.hand = ["bandages_lv0"]
    assert game.action_resolver.perform_action(
        "inv1", Action.PLAY, card_id="bandages_lv0") is True
    iid = next(i for i in inv.play_area
               if game.state.get_card_instance(i).card_id == "bandages_lv0")
    return inv, iid


class TestBandages:
    def test_card_registered(self, game):
        assert "bandages_lv0" in game.card_registry.registered_cards

    def test_heals_1_damage_per_supply(self, game):
        """同地点调查员受到2点伤害：花1补给治愈1点（净承伤1）。"""
        inv, iid = _play_bandages(game)
        game.damage_engine.deal_damage("inv1", damage=2)
        assert inv.damage == 1
        inst = game.state.get_card_instance(iid)
        assert inst.uses.get("suppliess") == 2

    def test_discards_when_supplies_run_out(self, game):
        """补给耗尽：绷带被弃置。"""
        inv, iid = _play_bandages(game)
        for _ in range(3):
            game.damage_engine.deal_damage("inv1", damage=1)
        assert inv.damage == 0  # 3次各治愈1点
        assert iid not in inv.play_area
        assert "bandages_lv0" in inv.discard
