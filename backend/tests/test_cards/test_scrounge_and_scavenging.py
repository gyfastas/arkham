"""Tests for Scrounge for Supplies (Level 0) and Scavenging (Level 2)."""

import pytest
from backend.cards.survivor.scrounge_for_supplies_lv0 import ScroungeForSupplies
from backend.cards.survivor.scavenging_lv2 import ScavengingLv2
from backend.models.enums import Action, ChaosTokenType, PlayerClass
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import (
    make_asset_data, make_event_data, make_investigator_data,
    make_location_data,
)
from backend.engine.game import Game
from backend.models.enums import CardType


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)
    loc = make_location_data(shroud=2)
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="scrounge_for_supplies_lv0", name="Scrounge for Supplies",
        cost=0, card_class=PlayerClass.SURVIVOR))
    g.register_card_data(make_asset_data(
        id="scavenging_lv2", name="Scavenging", cost=1,
        card_class=PlayerClass.SURVIVOR, traits=["talent"]))
    g.register_card_data(make_asset_data(id="item_lv0", traits=["item"]))
    g.register_card_data(make_asset_data(id="tome_lv0", traits=["tome"]))
    # 一张2级道具（回收类效果不应命中）
    lv2_item = make_asset_data(id="item_lv2", traits=["item"])
    lv2_item.level = 2
    g.register_card_data(lv2_item)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=3)
    g.card_registry.register_class(ScroungeForSupplies)
    g.card_registry.register_class(ScavengingLv2)
    return g


class TestScroungeForSupplies:
    def test_card_registered(self, game):
        assert "scrounge_for_supplies_lv0" in game.card_registry.registered_cards

    def test_recovers_first_level_zero_card(self, game):
        """取回弃牌堆第一张0级卡（跳过2级卡）。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["scrounge_for_supplies_lv0"]
        inv.discard = ["item_lv2", "item_lv0"]

        assert game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="scrounge_for_supplies_lv0") is True

        assert "item_lv0" in inv.hand
        assert "item_lv0" not in inv.discard
        assert "item_lv2" in inv.discard  # 高等级不动

    def test_no_level_zero_card_no_effect(self, game):
        inv = game.state.get_investigator("inv1")
        inv.hand = ["scrounge_for_supplies_lv0"]
        inv.discard = ["item_lv2"]

        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="scrounge_for_supplies_lv0")
        assert "item_lv2" not in inv.hand


def _equip_scavenging(game):
    inv = game.state.get_investigator("inv1")
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id="scavenging_lv2",
        owner_id="inv1", controller_id="inv1",
    )
    inv.play_area.append(iid)
    game.card_registry.activate_card("scavenging_lv2", iid, game.event_bus)
    return iid


class TestScavengingLv2:
    def test_card_registered(self, game):
        assert "scavenging_lv2" in game.card_registry.registered_cards

    def test_recovers_item_on_margin_2(self, game):
        """成功调查超出≥2：横置并取回弃牌堆中的道具。"""
        scav_id = _equip_scavenging(game)
        inv = game.state.get_investigator("inv1")
        inv.discard = ["tome_lv0", "item_lv0"]
        inv.actions_remaining = 3
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]  # 4 vs 2，超出2

        game.action_resolver.perform_action("inv1", Action.INVESTIGATE)

        assert "item_lv0" in inv.hand  # 第一张道具（跳过非道具）
        assert "tome_lv0" in inv.discard
        assert game.state.get_card_instance(scav_id).exhausted is True

    def test_no_trigger_below_margin(self, game):
        scav_id = _equip_scavenging(game)
        inv = game.state.get_investigator("inv1")
        inv.discard = ["item_lv0"]
        inv.actions_remaining = 3
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]  # 3 vs 2，仅超出1

        game.action_resolver.perform_action("inv1", Action.INVESTIGATE)

        assert "item_lv0" not in inv.hand
        assert game.state.get_card_instance(scav_id).exhausted is False
