"""Tests for Well-Maintained (Level 1). (05152)

快速事件：叠加到你控制的一张道具支援。被叠加的支援被丢弃后：它与其上
每张其它升级叠加都返回各自所有者的手牌。
"""

import pytest
from backend.cards.guardian.well_maintained_lv1 import WellMaintained
from backend.engine.game import Game
from backend.models.enums import Action, PlayerClass, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_event_data, make_investigator_data,
    make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_asset_data(
        id="flashlight_lv0", name="Flashlight", cost=2,
        slots=[SlotType.HAND], traits=["item", "tool"],
        uses={"supplies": 3}, health=1,
    ))
    g.register_card_data(make_event_data(
        id="well_maintained_lv1", name="Well-Maintained", cost=0,
        card_class=PlayerClass.GUARDIAN, fast=True,
    ))
    g.register_card_data(make_event_data(
        id="trusted_lv0", name="Trusted", cost=1,
        card_class=PlayerClass.GUARDIAN, fast=True,
    ))
    # make_event_data 不支持 traits；Trusted 卡面为 Upgrade
    g.state.get_card_data("trusted_lv0").traits = ["upgrade"]

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(WellMaintained)

    inv = g.state.get_investigator("inv1")
    inv.hand.append("well_maintained_lv1")
    inv.actions_remaining = 3
    return g


def _deploy_flashlight(game):
    game.state.cards_in_play["light_1"] = CardInstance(
        instance_id="light_1", card_id="flashlight_lv0",
        owner_id="inv1", controller_id="inv1",
        uses={"supplies": 3},
    )
    game.state.get_investigator("inv1").play_area.append("light_1")
    return game.state.cards_in_play["light_1"]


def _discard_flashlight(game):
    """手电筒被击败（1生命承1伤）→ 离场。"""
    game.damage_engine.deal_damage(
        "inv1", damage=1, damage_assignment={"light_1": 1},
    )


class TestWellMaintained:
    def test_attach_then_return_to_hand_on_discard(self, game):
        """叠加到手电筒；手电筒被丢弃后返回手牌，叠加实例清理。"""
        _deploy_flashlight(game)

        ok = game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="well_maintained_lv1",
        )
        assert ok is True
        inv = game.state.get_investigator("inv1")
        assert "well_maintained_lv1" in inv.discard  # 事件已结算入弃牌堆
        attachments = [ci for ci in game.state.cards_in_play.values()
                       if ci.attached_to == "light_1"]
        assert len(attachments) == 1

        _discard_flashlight(game)
        assert "flashlight_lv0" in inv.hand  # 返回手牌而非留在弃牌堆
        assert "flashlight_lv0" not in inv.discard
        assert [ci for ci in game.state.cards_in_play.values()
                if ci.attached_to == "light_1"] == []
        assert "well_maintained_lv1" in inv.discard  # 本卡不返回

    def test_returns_other_upgrade_attachments(self, game):
        """被叠加支援上的其它升级叠加一并返回所有者手牌。"""
        _deploy_flashlight(game)
        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="well_maintained_lv1",
        )
        inv = game.state.get_investigator("inv1")

        # 模拟另一张升级叠加（Trusted 事件已结算入弃牌堆，叠加实例在场）
        inv.discard.append("trusted_lv0")
        game.state.cards_in_play["trusted_att"] = CardInstance(
            instance_id="trusted_att", card_id="trusted_lv0",
            owner_id="inv1", controller_id="inv1", attached_to="light_1",
        )

        _discard_flashlight(game)
        assert "flashlight_lv0" in inv.hand
        assert "trusted_lv0" in inv.hand  # 升级叠加返回手牌
        assert "trusted_lv0" not in inv.discard
        assert game.state.get_card_instance("trusted_att") is None

    def test_no_item_fizzles(self, game):
        """场上没有道具支援：不结算叠加。"""
        ok = game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="well_maintained_lv1",
        )
        assert ok is True
        assert not any(ci.attached_to for ci
                       in game.state.cards_in_play.values())
