"""Tests for Dauntless Spirit (Level 1)."""

import pytest

from backend.cards.survivor.dauntless_spirit_lv1 import DauntlessSpirit
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, Skill
from backend.tests.conftest import (
    make_investigator_data, make_location_data, make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(willpower=2, combat=4, agility=1)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    ds = make_skill_data(id="dauntless_spirit_lv1")
    ds.skill_icons = {}  # 本卡无印刷图标（make_skill_data 默认补 wild）
    g.register_card_data(ds)
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(DauntlessSpirit)
    return g


def _committed_icons(game, skill):
    inv = game.state.get_investigator("inv1")
    inv.hand = ["dauntless_spirit_lv1"]
    game.chaos_bag.tokens = [ChaosTokenType.ZERO]
    result = game.skill_test_engine.run_test(
        "inv1", skill, 0, committed_card_ids=["dauntless_spirit_lv1"])
    return result


class TestDauntlessSpirit:
    def test_card_registered(self, game):
        assert "dauntless_spirit_lv1" in game.card_registry.registered_cards

    def test_willpower_test_gains_combat_icons(self, game):
        """意志检定：获得等同于战斗值(4)的图标。"""
        result = _committed_icons(game, Skill.WILLPOWER)
        assert result.committed_icons == 4
        assert result.modified_skill == 2 + 4  # 基础意志2 + 4图标

    def test_combat_test_gains_willpower_icons(self, game):
        """战斗检定：获得等同于意志值(2)的图标。"""
        result = _committed_icons(game, Skill.COMBAT)
        assert result.committed_icons == 2
        assert result.modified_skill == 4 + 2

    def test_agility_test_no_icons(self, game):
        """敏捷检定：无图标贡献。"""
        result = _committed_icons(game, Skill.AGILITY)
        assert result.committed_icons == 0
