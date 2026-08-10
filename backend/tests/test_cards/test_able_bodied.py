"""Tests for Able Bodied (Level 0)."""

import pytest

from backend.cards.survivor.able_bodied_lv0 import AbleBodied
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, Skill, SlotType
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
    make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(combat=3, agility=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_skill_data(
        id="able_bodied_lv0", skill_icons={"combat": 1, "agility": 1}))
    g.register_card_data(make_asset_data(
        id="test_item", name="Test Item", cost=1,
        slots=[SlotType.HAND], traits=["item"]))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(AbleBodied)
    return g


def _add_item(game, instance_id):
    inv = game.state.get_investigator("inv1")
    game.state.cards_in_play[instance_id] = CardInstance(
        instance_id=instance_id, card_id="test_item",
        owner_id="inv1", controller_id="inv1",
    )
    inv.play_area.append(instance_id)


def _commit_icons(game, skill):
    inv = game.state.get_investigator("inv1")
    inv.hand = ["able_bodied_lv0"]
    game.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]  # 结果无关紧要，只看图标
    result = game.skill_test_engine.run_test(
        "inv1", skill, 99, committed_card_ids=["able_bodied_lv0"])
    return result.committed_icons


class TestAbleBodied:
    def test_card_registered(self, game):
        assert "able_bodied_lv0" in game.card_registry.registered_cards

    def test_no_items_double_bonus(self, game):
        """控制0张道具：+战斗+战斗+敏捷+敏捷（战斗检定图标=1印刷+2加值）。"""
        assert _commit_icons(game, Skill.COMBAT) == 3

    def test_two_items_single_bonus(self, game):
        """控制2张道具：+战斗+敏捷（战斗检定图标=1印刷+1加值）。"""
        _add_item(game, "item_1")
        _add_item(game, "item_2")
        assert _commit_icons(game, Skill.COMBAT) == 2

    def test_three_items_no_bonus(self, game):
        """控制3张道具：仅印刷图标。"""
        for i in range(3):
            _add_item(game, f"item_{i}")
        assert _commit_icons(game, Skill.COMBAT) == 1

    def test_agility_test_also_benefits(self, game):
        assert _commit_icons(game, Skill.AGILITY) == 3

    def test_willpower_test_no_icons(self, game):
        """加值图标为战斗/敏捷，意志检定不受益。"""
        assert _commit_icons(game, Skill.WILLPOWER) == 0
