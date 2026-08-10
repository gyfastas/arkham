"""Tests for Guardian Angel (Level 0)."""

import pytest
from backend.cards.neutral.guardian_angel_lv0 import GuardianAngel
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data())
    g.register_card_data(make_investigator_data(id="inv2_data", name="Inv2"))
    g.register_card_data(make_location_data(connections=["loc2"]))
    g.register_card_data(make_location_data(id="loc2", name="Loc2", connections=["test_location"]))
    g.register_card_data(make_location_data(id="loc3", name="Loc3", connections=[]))
    g.register_card_data(make_asset_data(
        id="guardian_angel_lv0", name="Guardian Angel", cost=2, health=3,
    ))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_investigator("inv2", g.state.get_card_data("inv2_data"),
                       starting_location="loc2")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.add_location("loc2", g.state.get_card_data("loc2"))
    g.add_location("loc3", g.state.get_card_data("loc3"))
    g.card_registry.register_class(GuardianAngel)
    inv = g.state.get_investigator("inv1")
    inv.hand.append("guardian_angel_lv0")
    inv.resources = 5
    return g


def _play(game):
    game.action_resolver.perform_action(
        "inv1", Action.PLAY, card_id="guardian_angel_lv0",
    )
    return next(
        i for i in game.card_registry.active_instances.values()
        if isinstance(i, GuardianAngel)
    )


class TestGuardianAngel:
    def test_assigned_damage_adds_bless_tokens(self, game):
        """被分配伤害：向混沌袋加入等量[bless]。"""
        impl = _play(game)
        before = game.chaos_bag.tokens.count(ChaosTokenType.BLESS)
        actual = impl.assign_damage(game.state, 2)
        assert actual == 2
        inst = game.state.get_card_instance(impl.instance_id)
        assert inst.damage == 2
        assert game.chaos_bag.tokens.count(ChaosTokenType.BLESS) == before + 2

    def test_can_soak_for_connected_investigator(self, game):
        """可为同地点/相连地点的其他调查员承伤。"""
        impl = _play(game)
        assert impl.can_soak_for(game.state, "inv2") is True  # 相连地点

    def test_cannot_soak_for_unconnected(self, game):
        impl = _play(game)
        game.state.get_investigator("inv2").location_id = "loc3"
        assert impl.can_soak_for(game.state, "inv2") is False
