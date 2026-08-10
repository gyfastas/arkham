"""Tests for Police Badge (Level 2)."""

import pytest
from backend.cards.guardian.police_badge_lv2 import PoliceBadge
from backend.models.enums import SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import make_asset_data, make_investigator_data


@pytest.fixture
def badge_game(game):
    game.register_card_data(make_asset_data(
        id="police_badge_lv2", name="Police Badge",
        slots=[SlotType.ACCESSORY], traits=["item"],
    ))
    inv = game.state.get_investigator("test_investigator")
    inst = CardInstance(
        instance_id="badge_1", card_id="police_badge_lv2",
        owner_id="test_investigator", controller_id="test_investigator",
    )
    game.state.cards_in_play["badge_1"] = inst
    inv.play_area.append("badge_1")

    game.card_registry.register_class(PoliceBadge)
    game.card_registry.activate_card("police_badge_lv2", "badge_1", game.event_bus)
    return game


class TestPoliceBadge:
    def test_card_id(self):
        assert PoliceBadge.card_id == "police_badge_lv2"

    def test_has_willpower_bonus_handler(self):
        """Police Badge should have a SKILL_VALUE_DETERMINED handler for willpower."""
        impl = PoliceBadge("test_instance")
        assert hasattr(impl, 'willpower_bonus')

    def test_discard_grants_2_actions(self, badge_game):
        """弃置警徽：该调查员本回合+2行动，警徽进入弃牌堆。"""
        game = badge_game
        inv = game.state.get_investigator("test_investigator")
        inv.actions_remaining = 1

        impl = game.card_registry.active_instances.get("badge_1")
        assert impl.activate_discard_actions(game.state, "test_investigator") is True
        assert inv.actions_remaining == 3
        assert "badge_1" not in inv.play_area
        assert "police_badge_lv2" in inv.discard
        assert "badge_1" not in game.state.cards_in_play

    def test_discard_grants_actions_to_other_investigator(self, badge_game):
        """可指定同地点的其他调查员获得行动。"""
        game = badge_game
        other_data = make_investigator_data(id="inv2")
        game.register_card_data(other_data)
        game.add_investigator("inv2", other_data, starting_location="test_location")
        other = game.state.get_investigator("inv2")
        other.actions_remaining = 0

        impl = game.card_registry.active_instances.get("badge_1")
        assert impl.activate_discard_actions(
            game.state, "test_investigator",
            target_investigator_id="inv2") is True
        assert other.actions_remaining == 2

    def test_target_must_be_at_location(self, badge_game):
        """目标调查员不在同地点时不能启动（警徽不弃置）。"""
        game = badge_game
        other_data = make_investigator_data(id="inv2")
        game.register_card_data(other_data)
        game.add_investigator("inv2", other_data, starting_location="test_location")
        other = game.state.get_investigator("inv2")
        other.location_id = "elsewhere"

        impl = game.card_registry.active_instances.get("badge_1")
        assert impl.activate_discard_actions(
            game.state, "test_investigator",
            target_investigator_id="inv2") is False
        inv = game.state.get_investigator("test_investigator")
        assert "badge_1" in inv.play_area

    def test_not_in_play_cannot_activate(self, badge_game):
        """警徽不在场时不能启动。"""
        game = badge_game
        inv = game.state.get_investigator("test_investigator")
        inv.play_area.remove("badge_1")

        impl = game.card_registry.active_instances.get("badge_1")
        assert impl.activate_discard_actions(game.state, "test_investigator") is False
