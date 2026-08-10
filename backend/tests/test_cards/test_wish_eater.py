"""Tests for Wish Eater (Level 0). (06277)

[反应]揭示 skull/cultist/tablet/elder_thing 标记时花费1充能：取消该标记，
治愈1伤害1恐惧。强制：无充能时交换为空虚项链。
"""

import pytest
from backend.cards.guardian.wish_eater_lv0 import WishEater
from backend.engine.game import Game
from backend.models.enums import (
    ChaosTokenType, PlayerClass, Skill, SlotType,
)
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(willpower=3)
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_asset_data(
        id="wish_eater_lv0", name="Wish Eater", cost=None,
        card_class=PlayerClass.GUARDIAN,
        slots=[SlotType.ACCESSORY], traits=["item", "relic", "blessed"],
    ))
    g.register_card_data(make_asset_data(
        id="empty_vessel_lv4", name="Empty Vessel", cost=1,
        card_class=PlayerClass.GUARDIAN,
        slots=[SlotType.ACCESSORY], traits=["item", "relic", "blessed"],
        uses={"charges": 0},
    ))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(WishEater)
    return g


def _deploy_wish_eater(game, charges):
    game.state.cards_in_play["we_1"] = CardInstance(
        instance_id="we_1", card_id="wish_eater_lv0",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.ACCESSORY], uses={"charges": charges},
    )
    inv = game.state.get_investigator("inv1")
    inv.play_area.append("we_1")
    game.card_registry.activate_card("wish_eater_lv0", "we_1", game.event_bus)
    return game.state.cards_in_play["we_1"]


class TestWishEater:
    def test_cancel_bad_token_and_heal(self, game):
        """揭示骷髅标记：自动花1充能取消（修正归0）并治愈1伤害1恐惧。"""
        we = _deploy_wish_eater(game, charges=2)
        inv = game.state.get_investigator("inv1")
        inv.damage = 1
        inv.horror = 1
        game.chaos_bag.tokens = [ChaosTokenType.SKULL]

        result = game.skill_test_engine.run_test("inv1", Skill.WILLPOWER, 3)

        assert we.uses["charges"] == 1  # 花了1充能
        assert inv.damage == 0 and inv.horror == 0  # 各治愈1
        assert result.token_modifier == 0  # 标记修正被取消
        assert result.success is True  # 3 vs 3
        assert any("食愿项链" in m for m in game.state.effect_log)
        # 仍有充能：不交换
        assert game.state.get_card_instance("we_1") is not None

    def test_no_cancel_on_safe_token(self, game):
        """揭示普通数值标记：不触发，充能不变。"""
        we = _deploy_wish_eater(game, charges=2)
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]

        game.skill_test_engine.run_test("inv1", Skill.WILLPOWER, 3)
        assert we.uses["charges"] == 2

    def test_forced_swap_when_charges_empty(self, game):
        """最后一充能耗尽：强制交换为空虚项链（0充能，同 accessory 槽）。"""
        _deploy_wish_eater(game, charges=1)
        inv = game.state.get_investigator("inv1")
        game.chaos_bag.tokens = [ChaosTokenType.CULTIST]

        game.skill_test_engine.run_test("inv1", Skill.WILLPOWER, 3)

        assert game.state.get_card_instance("we_1") is None
        assert "we_1" not in inv.play_area
        assert "wish_eater_lv0" not in inv.discard  # 回绑定堆而非弃牌堆
        vessels = [ci for ci in (game.state.get_card_instance(i)
                                 for i in inv.play_area)
                   if ci is not None and ci.card_id == "empty_vessel_lv4"]
        assert len(vessels) == 1
        assert vessels[0].uses.get("charges") == 0
        assert vessels[0].slot_used == [SlotType.ACCESSORY]
