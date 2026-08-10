"""Tests for Jury-Rig (Level 0)."""

import pytest
from backend.cards.survivor.jury_rig_lv0 import JuryRig
from backend.models.enums import Action, ChaosTokenType, PlayerClass, Skill, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_event_data, make_investigator_data,
    make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="jury_rig_lv0", name="Jury-Rig", cost=0,
        card_class=PlayerClass.SURVIVOR))
    g.register_card_data(make_asset_data(
        id="test_item", name="Test Item", traits=["item"],
        slots=[SlotType.HAND]))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(JuryRig)
    return g


def _put_item_in_play(game):
    inv = game.state.get_investigator("inv1")
    iid = game.state.next_instance_id()
    game.state.cards_in_play[iid] = CardInstance(
        instance_id=iid, card_id="test_item",
        owner_id="inv1", controller_id="inv1", slot_used=[SlotType.HAND],
    )
    inv.play_area.append(iid)
    return iid


def _play_jury_rig(game):
    inv = game.state.get_investigator("inv1")
    inv.hand = ["jury_rig_lv0"]
    inv.actions_remaining = 3
    assert game.action_resolver.perform_action(
        "inv1", Action.PLAY, card_id="jury_rig_lv0") is True
    # 找到刚激活的事件实现实例
    for iid, impl in game.card_registry.active_instances.items():
        if impl.card_id == "jury_rig_lv0":
            return impl
    raise AssertionError("jury_rig impl not active")


class TestJuryRig:
    def test_card_registered(self, game):
        assert "jury_rig_lv0" in game.card_registry.registered_cards

    def test_attaches_to_item_and_boosts_its_test(self, game):
        """打出叠加到道具；花耐久使该资产的检定 +2。"""
        item_id = _put_item_in_play(game)
        impl = _play_jury_rig(game)

        state = game.state.scenario.vars["jury_rig"]
        assert state["asset"] == item_id
        assert state["durability"] == 3

        assert impl.spend(game.state, "inv1") is True
        assert state["durability"] == 2

        # 被附加资产发起的检定（source=道具实例）：+2
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test(
            "inv1", Skill.INTELLECT, 5, source_instance_id=item_id)
        assert result.modified_skill == 5  # 3 + 2
        assert result.success is True

    def test_boost_not_applied_to_other_sources(self, game):
        """加值只作用于被附加资产的检定。"""
        item_id = _put_item_in_play(game)
        impl = _play_jury_rig(game)
        impl.spend(game.state, "inv1")

        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test(
            "inv1", Skill.INTELLECT, 5, source_instance_id="other_source")
        assert result.modified_skill == 3

    def test_fizzles_without_item(self, game):
        """没有可叠加的道具时效果落空。"""
        _play_jury_rig(game)
        assert "jury_rig" not in game.state.scenario.vars
