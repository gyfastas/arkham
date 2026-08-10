"""Tests for Hypnotic Therapy (Level 0)."""

import pytest
from backend.cards.neutral.hypnotic_therapy_lv0 import HypnoticTherapy
from backend.engine.game import Game
from backend.models.enums import Action, ChaosTokenType
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    g.register_card_data(make_investigator_data(intellect=4))
    g.register_card_data(make_location_data())
    g.register_card_data(make_asset_data(
        id="hypnotic_therapy_lv0", name="Hypnotic Therapy", cost=2,
    ))
    g.add_investigator("inv1", g.state.get_card_data("test_investigator"),
                       starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"))
    g.card_registry.register_class(HypnoticTherapy)
    inv = g.state.get_investigator("inv1")
    inv.hand.append("hypnotic_therapy_lv0")
    inv.resources = 5
    inv.horror = 2
    inv.deck = ["guts_lv0"]
    # 袋中只有 +1：智力4+1 vs 难度2 必成功
    g.chaos_bag.tokens = [ChaosTokenType.PLUS_1]
    return g


def _play(game):
    game.action_resolver.perform_action(
        "inv1", Action.PLAY, card_id="hypnotic_therapy_lv0",
    )
    return next(
        i for i in game.card_registry.active_instances.values()
        if isinstance(i, HypnoticTherapy)
    )


class TestHypnoticTherapy:
    def test_activate_heals_horror_and_draws(self, game):
        """[行动] 智力(2)成功：治愈1恐惧，抽1张牌。"""
        impl = _play(game)
        inv = game.state.get_investigator("inv1")
        assert impl.activate(game, "inv1") is True
        assert inv.horror == 1
        assert "guts_lv0" in inv.hand
        inst = game.state.get_card_instance(impl.instance_id)
        assert inst.exhausted is True

    def test_amplify_other_heal(self, game):
        """[reaction] 其他效果治愈恐惧后：横置额外治愈1点。"""
        impl = _play(game)
        inv = game.state.get_investigator("inv1")
        assert impl.amplify_heal(game.state, "inv1", "inv1") is True
        assert inv.horror == 1
        inst = game.state.get_card_instance(impl.instance_id)
        assert inst.exhausted is True
