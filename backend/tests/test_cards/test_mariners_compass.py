"""Tests for Mariner's Compass (Level 0)."""

import pytest
from backend.cards.survivor.mariners_compass_lv0 import MarinersCompass
from backend.models.enums import Action, ChaosTokenType, PlayerClass, Skill, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)
    loc = make_location_data(shroud=2)
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="mariners_compass_lv0", name="Mariner's Compass", cost=3,
        card_class=PlayerClass.SURVIVOR, slots=[SlotType.HAND],
        traits=["item", "tool"],
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=3)
    g.card_registry.register_class(MarinersCompass)
    return g


def _equip_compass(game):
    inv = game.state.get_investigator("inv1")
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id="mariners_compass_lv0",
        owner_id="inv1", controller_id="inv1", slot_used=[SlotType.HAND],
    )
    inv.play_area.append(iid)
    game.card_registry.activate_card(
        "mariners_compass_lv0", iid, game.event_bus)
    return iid


def _investigate(game, token):
    inv = game.state.get_investigator("inv1")
    inv.actions_remaining = 3
    game.chaos_bag.tokens = [token]
    game.action_resolver.perform_action("inv1", Action.INVESTIGATE)
    return game.skill_test_engine._last_result


class TestMarinersCompass:
    def test_card_registered(self, game):
        assert "mariners_compass_lv0" in game.card_registry.registered_cards

    def test_bonus_clue_when_no_resources(self, game):
        """罗盘调查成功且资源池为0：额外发现1线索（并横置罗盘）。"""
        compass_id = _equip_compass(game)
        inv = game.state.get_investigator("inv1")
        inv.resources = 0
        impl = game.card_registry.active_instances[compass_id]

        assert impl.activate(game.state, "inv1") is True
        assert game.state.get_card_instance(compass_id).exhausted is True

        result = _investigate(game, ChaosTokenType.PLUS_1)  # 4 vs 2 成功

        assert result.success is True
        assert inv.clues == 2  # 基础1 + 罗盘1
        loc = game.state.get_location("test_location")
        assert loc.clues == 1

    def test_no_bonus_clue_with_resources(self, game):
        compass_id = _equip_compass(game)
        inv = game.state.get_investigator("inv1")
        inv.resources = 2
        impl = game.card_registry.active_instances[compass_id]
        impl.activate(game.state, "inv1")

        result = _investigate(game, ChaosTokenType.PLUS_1)

        assert result.success is True
        assert inv.clues == 1

    def test_spend_up_to_three_for_plus_1_each(self, game):
        """每次调查限3次花1资源 +1 智力。"""
        compass_id = _equip_compass(game)
        inv = game.state.get_investigator("inv1")
        inv.resources = 5
        impl = game.card_registry.active_instances[compass_id]
        impl.activate(game.state, "inv1")

        for _ in range(3):
            assert impl.spend(game.state, "inv1", Skill.INTELLECT) is True
        assert impl.spend(game.state, "inv1", Skill.INTELLECT) is False

        result = _investigate(game, ChaosTokenType.ZERO)
        assert result.modified_skill == 3 + 3  # 3×(+1)
        assert inv.resources == 2  # 花费3，资源非0无额外线索
        assert inv.clues == 1

    def test_spend_requires_armed_investigation(self, game):
        """未启动罗盘调查时不能花费。"""
        _equip_compass(game)
        inv = game.state.get_investigator("inv1")
        impl = game.card_registry.active_instances[inv.play_area[-1]]
        assert impl.spend(game.state, "inv1", Skill.INTELLECT) is False
