"""Tests for Livre d'Eibon (Level 0)."""

import pytest
from backend.cards.neutral.livre_deibon_lv0 import LivreDeibon
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType, Skill
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
    make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data(willpower=3))
    g.register_card_data(make_location_data())
    g.register_card_data(make_asset_data(
        id="livre_deibon_lv0", name="Livre d'Eibon", cost=2,
    ))
    g.register_card_data(make_skill_data(
        id="test_skill", name="Test Skill",
        skill_icons={"willpower": 1},
    ))
    g.register_card_data(make_skill_data(id="guts_lv0", name="Guts"))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(LivreDeibon)
    inv = g.state.get_investigator("inv1")
    inv.hand.append("livre_deibon_lv0")
    inv.resources = 5
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]
    return g


def _play(game):
    game.action_resolver.perform_action(
        "inv1", Action.PLAY, card_id="livre_deibon_lv0",
    )
    return next(
        i for i in game.card_registry.active_instances.values()
        if isinstance(i, LivreDeibon)
    )


class TestLivreDeibon:
    def test_swap_top_deck_with_hand(self, game):
        """[fast] 横置：牌库顶牌与1张手牌交换。"""
        impl = _play(game)
        inv = game.state.get_investigator("inv1")
        inv.deck = ["test_skill", "guts_lv0"]
        inv.hand.append("guts_lv0")

        assert impl.activate_swap(game.state, "inv1",
                                  hand_card_id="guts_lv0") is True
        assert inv.deck[0] == "guts_lv0"
        assert "test_skill" in inv.hand
        inst = game.state.get_card_instance(impl.instance_id)
        assert inst.exhausted is True

    def test_commit_top_deck_to_test(self, game):
        """[fast] 横置：牌库顶牌投入同地点检定（+1意志图标），结算后弃置。"""
        impl = _play(game)
        inv = game.state.get_investigator("inv1")
        inv.deck = ["test_skill"]
        inst = game.state.get_card_instance(impl.instance_id)
        inst.exhausted = False

        assert impl.activate_commit(game.state, "inv1") is True
        assert inv.deck == []
        result = game.skill_test_engine.run_test("inv1", Skill.WILLPOWER, 4)
        # 3意志 + 1图标 + 0标记 = 4 成功
        assert result.committed_icons == 1
        assert result.success is True
        assert "test_skill" in inv.discard
