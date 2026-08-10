"""Tests for Teamwork (Level 0)."""

import pytest
from backend.cards.guardian.teamwork_lv0 import Teamwork
from backend.models.enums import SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import make_asset_data, make_investigator_data


@pytest.fixture
def tw_game(game):
    game.register_card_data(make_asset_data(
        id="flashlight_lv0", name="Flashlight",
        slots=[SlotType.HAND], traits=["item", "tool"],
    ))
    other_data = make_investigator_data(id="inv2")
    game.register_card_data(other_data)
    game.add_investigator("inv2", other_data, starting_location="test_location")

    inv = game.state.get_investigator("test_investigator")
    light = CardInstance(
        instance_id="light_1", card_id="flashlight_lv0",
        owner_id="test_investigator", controller_id="test_investigator",
    )
    game.state.cards_in_play["light_1"] = light
    inv.play_area.append("light_1")
    return game


class TestTeamwork:
    def test_card_id(self):
        assert Teamwork.card_id == "teamwork_lv0"

    def test_trade_resources(self, tw_game):
        """同地点调查员之间转移资源。"""
        inv1 = tw_game.state.get_investigator("test_investigator")
        inv2 = tw_game.state.get_investigator("inv2")
        inv1.resources = 5
        inv2.resources = 1

        assert Teamwork.trade_resources(
            tw_game.state, "test_investigator", "inv2", 3) is True
        assert inv1.resources == 2
        assert inv2.resources == 4

    def test_trade_asset_keeps_ownership(self, tw_game):
        """交易只改变控制权，所有权不变（ownership ≠ control）。"""
        inv1 = tw_game.state.get_investigator("test_investigator")
        inv2 = tw_game.state.get_investigator("inv2")

        assert Teamwork.trade_asset(
            tw_game.state, "test_investigator", "inv2", "light_1") is True
        light = tw_game.state.get_card_instance("light_1")
        assert light.controller_id == "inv2"
        assert light.owner_id == "test_investigator"  # 所有权不变
        assert "light_1" not in inv1.play_area
        assert "light_1" in inv2.play_area

    def test_trade_requires_same_location(self, tw_game):
        """不同地点不能交易。"""
        inv2 = tw_game.state.get_investigator("inv2")
        inv2.location_id = "elsewhere"
        assert Teamwork.trade_asset(
            tw_game.state, "test_investigator", "inv2", "light_1") is False
