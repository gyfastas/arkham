"""Tests for Favor of the Sun (Level 1)."""

import pytest
from backend.cards.neutral.favor_of_the_sun_lv1 import FavorOfTheSun
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, Skill
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data())
    g.register_card_data(make_location_data())
    g.register_card_data(make_asset_data(
        id="favor_of_the_sun_lv1", name="Favor of the Sun", cost=2,
    ))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(FavorOfTheSun)
    inv = g.state.get_investigator("inv1")
    inv.hand.append("favor_of_the_sun_lv1")
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]
    for _ in range(3):
        g.chaos_bag.add_token(ChaosTokenType.BLESS)
    return g


class TestFavorOfTheSun:
    def test_seal_and_resolve_bless(self, game):
        """进场封印3个[bless]；横置后揭示改为按bless(+2)结算，无资源。"""
        inv = game.state.get_investigator("inv1")
        inv.resources = 5
        game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="favor_of_the_sun_lv1",
        )
        impl = next(
            i for i in game.card_registry.active_instances.values()
            if isinstance(i, FavorOfTheSun)
        )
        inst = game.state.get_card_instance(impl.instance_id)
        assert inst.uses["sealed"] == 3
        assert game.chaos_bag.sealed.count(ChaosTokenType.BLESS) == 3

        resources_before = inv.resources
        assert impl.activate_resolve_sealed(game.state, "inv1") is True
        result = game.skill_test_engine.run_test("inv1", Skill.COMBAT, 5)
        # 袋中只有 0（修正0），被替换为bless(+2)：3+0+2 >= 5 成功
        assert result.token_modifier == 2
        assert result.success is True
        assert inv.resources == resources_before  # 日之恩惠不给资源
