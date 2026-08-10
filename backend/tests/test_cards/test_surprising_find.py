"""Tests for Surprising Find (Level 1).

官方：多重。[反应]在你查找牌堆时若本卡在被查找卡牌中：放置入你的游戏
区域。你必须将其投入到你执行的下一次符合条件的技能检定。若该检定
成功，抽1张牌。
"""

import pytest

from backend.cards.seeker.surprising_find_lv1 import SurprisingFind
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, Skill
from backend.tests.conftest import (
    make_investigator_data, make_location_data, make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test_surprising_find")
    g.chaos_bag.seed(42)
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]

    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a")
    g.register_card_data(loc_data)
    g.add_investigator(
        "player", inv_data,
        deck=["surprising_find_lv1", "card_a"],
        starting_location="loc_a",
    )
    g.add_location("loc_a", loc_data, clues=0)

    g.register_card_data(make_skill_data(
        id="surprising_find_lv1", skill_icons={"wild": 1}))
    g.card_registry.register_class(SurprisingFind)
    return g


def _activate(game):
    impl = game.card_registry.activate_card(
        "surprising_find_lv1", "impl_sf", game.event_bus,
        chaos_bag=game.chaos_bag)
    return impl


class TestSurprisingFind:
    def test_searched_commits_next_test_and_draws(self, game):
        """被检索到：入场，下次检定自动+1 wild，成功抽1张，随后离场弃置。"""
        inv = game.state.get_investigator("player")
        impl = _activate(game)
        assert impl.on_searched(game.state, "player") is True
        assert "surprising_find_lv1" not in inv.deck
        assert len(inv.play_area) == 1

        # 智力4难度：3 + 1(强制投入wild) = 4 成功
        result = game.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.INTELLECT,
            difficulty=4,
        )
        assert result.success is True
        assert result.committed_icons == 1
        assert "card_a" in inv.hand  # 成功抽1张
        # 检定结束后离场入弃牌堆
        assert inv.play_area == []
        assert "surprising_find_lv1" in inv.discard

    def test_not_searched_no_effect(self, game):
        """未被检索到时检定无加值。"""
        _activate(game)
        result = game.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.INTELLECT,
            difficulty=4,
        )
        assert result.committed_icons == 0
        assert result.success is False  # 3 < 4
