"""Tests for Nightmare Bauble (Level 3)."""

import pytest
from backend.cards.survivor.nightmare_bauble_lv3 import NightmareBauble
from backend.models.enums import (
    Action, ChaosTokenType, PlayerClass, Skill, SlotType,
)
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
    make_skill_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_asset_data(
        id="nightmare_bauble_lv3", name="Nightmare Bauble", cost=1,
        card_class=PlayerClass.SURVIVOR, slots=[SlotType.ACCESSORY],
        traits=["item", "charm", "cursed"]))
    g.register_card_data(make_skill_data(
        id="dream_parasite_lv0", name="Dream Parasite",
        card_class=PlayerClass.NEUTRAL, skill_icons={"wild": 2}))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(NightmareBauble)
    return g


def _play_bauble(game):
    inv = game.state.get_investigator("inv1")
    inv.hand = ["nightmare_bauble_lv3"]
    inv.resources = 3
    assert game.action_resolver.perform_action(
        "inv1", Action.PLAY, card_id="nightmare_bauble_lv3") is True
    return inv.play_area[-1]


class TestNightmareBauble:
    def test_card_registered(self, game):
        assert "nightmare_bauble_lv3" in game.card_registry.registered_cards

    def test_enters_play_with_3_parasites(self, game):
        """入场后附加3张梦寄生虫。"""
        bauble_id = _play_bauble(game)
        impl = game.card_registry.active_instances[bauble_id]
        assert impl._parasites == 3

    def test_cancel_auto_fail_by_shuffling_parasite(self, game):
        """揭示自动失败：洗1张梦寄生虫回牌库并取消该标记。"""
        bauble_id = _play_bauble(game)
        impl = game.card_registry.active_instances[bauble_id]
        inv = game.state.get_investigator("inv1")
        inv.deck = []

        game.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]
        # 战斗3 vs 难度3：自动失败被取消 → 3 ≥ 3 成功
        result = game.skill_test_engine.run_test("inv1", Skill.COMBAT, 3)

        assert result.success is True
        assert result.auto_fail is False
        assert impl._parasites == 2
        assert "dream_parasite_lv0" in inv.deck

    def test_no_cancel_without_parasites(self, game):
        bauble_id = _play_bauble(game)
        impl = game.card_registry.active_instances[bauble_id]
        impl._parasites = 0

        game.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]
        result = game.skill_test_engine.run_test("inv1", Skill.COMBAT, 3)
        assert result.success is False
        assert result.auto_fail is True
