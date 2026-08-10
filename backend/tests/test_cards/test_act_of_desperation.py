"""Tests for Act of Desperation (Level 0)."""

import pytest

from backend.cards.survivor.act_of_desperation_lv0 import ActOfDesperation
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_enemy_data, make_event_data,
    make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="act_of_desperation_lv0", name="Act of Desperation", cost=0))
    g.register_card_data(make_asset_data(
        id="test_item", name="Expensive Item", cost=3,
        slots=[SlotType.HAND], traits=["item"]))
    g.register_card_data(make_enemy_data(fight=3, health=10, evade=3))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(ActOfDesperation)
    return g


def _setup(game, in_play=True):
    inv = game.state.get_investigator("inv1")
    inv.resources = 5
    if in_play:
        game.state.cards_in_play["item_1"] = CardInstance(
            instance_id="item_1", card_id="test_item",
            owner_id="inv1", controller_id="inv1",
        )
        inv.play_area.append("item_1")
    else:
        inv.hand.append("test_item")
    game.state.cards_in_play["enemy_1"] = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    inv.threat_area.append("enemy_1")
    return inv


class TestActOfDesperation:
    def test_card_registered(self, game):
        assert "act_of_desperation_lv0" in game.card_registry.registered_cards

    def test_discard_from_play_grants_x_on_success(self, game):
        """丢弃游戏区道具：+X战斗、+1伤害，成功后获得X资源。"""
        inv = _setup(game, in_play=True)
        inv.hand.append("act_of_desperation_lv0")
        assert game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="act_of_desperation_lv0") is True
        # 额外费用：游戏区道具已丢弃
        assert "item_1" not in inv.play_area
        assert "test_item" in inv.discard
        assert inv.active_effects["act_of_desperation_lv0"]["x"] == 3

        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        resources_before = inv.resources
        assert game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1") is True
        enemy = game.state.get_card_instance("enemy_1")
        # 基础1 + 卡面+1 = 2伤害
        assert enemy.damage == 2
        # 成功且道具来自游戏区：获得X=3资源
        assert inv.resources == resources_before + 3

    def test_discard_from_hand_no_resource_gain(self, game):
        """丢弃手牌中的道具：攻击仍有加值，但成功不获得资源。"""
        inv = _setup(game, in_play=False)
        inv.hand.append("act_of_desperation_lv0")
        assert game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="act_of_desperation_lv0") is True
        assert "test_item" in inv.discard
        assert inv.active_effects["act_of_desperation_lv0"] == {
            "x": 3, "from_play": False}

        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        resources_before = inv.resources
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT, enemy_instance_id="enemy_1")
        enemy = game.state.get_card_instance("enemy_1")
        assert enemy.damage == 2
        assert inv.resources == resources_before

    def test_no_legal_item_no_effect(self, game):
        """无合法道具：不武装攻击加值。"""
        inv = game.state.get_investigator("inv1")
        inv.resources = 5
        inv.hand = ["act_of_desperation_lv0"]
        assert game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="act_of_desperation_lv0") is True
        assert not getattr(inv, "active_effects", {}).get(
            "act_of_desperation_lv0")
