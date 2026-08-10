"""Tests for Hemispheric Map (Level 3)."""

import pytest
from backend.cards.neutral.hemispheric_map_lv3 import HemisphericMap
from backend.engine.game import Game
from backend.models.enums import Action
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


def _build_game(connections):
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data())
    g.register_card_data(make_location_data(connections=connections))
    g.register_card_data(make_asset_data(
        id="hemispheric_map_lv3", name="Hemispheric Map", cost=2,
    ))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(HemisphericMap)
    inv = g.state.get_investigator("inv1")
    inv.hand.append("hemispheric_map_lv3")
    inv.resources = 5
    g.action_resolver.perform_action(
        "inv1", Action.PLAY, card_id="hemispheric_map_lv3",
    )
    return g


class TestHemisphericMap:
    def test_no_bonus_with_fewer_than_2_connections(self):
        g = _build_game(["loc2"])
        assert g.preview_skill_bonuses("inv1") == {}

    def test_bonus_with_2_connections(self):
        g = _build_game(["a", "b"])
        bonuses = g.preview_skill_bonuses("inv1")
        assert bonuses["willpower"] == 1
        assert bonuses["intellect"] == 1
        assert "combat" not in bonuses

    def test_double_bonus_with_4_connections(self):
        g = _build_game(["a", "b", "c", "d"])
        bonuses = g.preview_skill_bonuses("inv1")
        assert bonuses["willpower"] == 2
        assert bonuses["intellect"] == 2
