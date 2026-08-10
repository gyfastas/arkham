"""Tests for Favor of the Moon (Level 1)."""

import pytest
from backend.cards.neutral.favor_of_the_moon_lv1 import FavorOfTheMoon
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
        id="favor_of_the_moon_lv1", name="Favor of the Moon", cost=1,
    ))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(FavorOfTheMoon)
    inv = g.state.get_investigator("inv1")
    inv.hand.append("favor_of_the_moon_lv1")
    # 袋中放入3个curse供封印；剩余标记固定为 0，保证检定结果可预期
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]
    for _ in range(3):
        g.chaos_bag.add_token(ChaosTokenType.CURSE)
    return g


def _play(game):
    inv = game.state.get_investigator("inv1")
    inv.resources = 5
    game.action_resolver.perform_action(
        "inv1", Action.PLAY, card_id="favor_of_the_moon_lv1",
    )
    return next(
        i for i in game.card_registry.active_instances.values()
        if isinstance(i, FavorOfTheMoon)
    )


class TestFavorOfTheMoon:
    def test_seal_up_to_3_curse_on_enter_play(self, game):
        """进场：封印至多3个[curse]，记录于实例。"""
        _play(game)
        inst = next(
            i for i in game.state.cards_in_play.values()
            if i.card_id == "favor_of_the_moon_lv1"
        )
        assert inst.uses["sealed"] == 3
        assert game.chaos_bag.sealed.count(ChaosTokenType.CURSE) == 3
        assert ChaosTokenType.CURSE not in game.chaos_bag.tokens

    def test_resolve_sealed_token_instead(self, game):
        """横置后揭示标记改为按封印的curse(-2)结算，并获得1资源。"""
        impl = _play(game)
        inv = game.state.get_investigator("inv1")
        resources_before = inv.resources
        assert impl.activate_resolve_sealed(game.state, "inv1") is True

        result = game.skill_test_engine.run_test("inv1", Skill.COMBAT, 3)
        # 袋中只有 0（修正0），被替换为curse(-2)：3+0-2 < 3 失败
        assert result.token_modifier == -2
        assert result.success is False
        assert inv.resources == resources_before + 1
        inst = game.state.get_card_instance(impl.instance_id)
        assert inst.uses["sealed"] == 2
        assert game.chaos_bag.sealed.count(ChaosTokenType.CURSE) == 2

    def test_discarded_when_sealed_runs_out(self, game):
        """封印耗尽时丢弃。"""
        impl = _play(game)
        inst = game.state.get_card_instance(impl.instance_id)
        inst.uses["sealed"] = 1
        assert impl.activate_resolve_sealed(game.state, "inv1") is True
        game.skill_test_engine.run_test("inv1", Skill.COMBAT, 3)
        inv = game.state.get_investigator("inv1")
        assert impl.instance_id not in inv.play_area
        assert "favor_of_the_moon_lv1" in inv.discard
