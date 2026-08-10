"""Tests for the four Desperate skills (Path to Carcosa, Neutral):
Say Your Prayers / Desperate Search / Reckless Assault / Run For Your Life.
"""

import pytest

from backend.cards.neutral.desperate_search_lv0 import DesperateSearch
from backend.cards.neutral.reckless_assault_lv0 import RecklessAssault
from backend.cards.neutral.run_for_your_life_lv0 import RunForYourLife
from backend.cards.neutral.say_your_prayers_lv0 import SayYourPrayers
from backend.models.enums import ChaosTokenType, Skill
from backend.tests.conftest import make_skill_data

CARDS = [
    ("say_your_prayers_lv0", SayYourPrayers, Skill.WILLPOWER, "willpower"),
    ("desperate_search_lv0", DesperateSearch, Skill.INTELLECT, "intellect"),
    ("reckless_assault_lv0", RecklessAssault, Skill.COMBAT, "combat"),
    ("run_for_your_life_lv0", RunForYourLife, Skill.AGILITY, "agility"),
]


class TestCommitRestriction:
    @pytest.mark.parametrize("card_id,cls,skill,icon_key", CARDS)
    def test_can_commit_only_at_low_sanity(self, game, card_id, cls, skill, icon_key):
        """剩余神智≤3才可投入。"""
        inv = game.state.get_investigator("test_investigator")
        impl = cls("inst1")
        assert impl.can_commit(game.state, "test_investigator") is False  # 7/7
        inv.horror = 3
        assert impl.can_commit(game.state, "test_investigator") is False  # 剩4
        inv.horror = 4
        assert impl.can_commit(game.state, "test_investigator") is True  # 剩3

    @pytest.mark.parametrize("card_id,cls,skill,icon_key", CARDS)
    def test_unknown_investigator_cannot_commit(self, game, card_id, cls, skill, icon_key):
        assert cls("inst1").can_commit(game.state, "nobody") is False


class TestSkillIcons:
    @pytest.mark.parametrize("card_id,cls,skill,icon_key", CARDS)
    def test_four_icons_counted_in_test(self, game, card_id, cls, skill, icon_key):
        """投入后提供4个对应图标：3基础+4图标=7 过难度4；不投入则失败。"""
        game.register_card_data(make_skill_data(id=card_id, skill_icons={icon_key: 4}))
        inv = game.state.get_investigator("test_investigator")
        inv.hand.append(card_id)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        result = game.skill_test_engine.run_test(
            "test_investigator", skill, 4, committed_card_ids=[card_id],
        )
        assert result.success
        assert result.committed_icons == 4
        assert card_id in inv.discard  # 检定结束后投入牌入弃牌堆

    @pytest.mark.parametrize("card_id,cls,skill,icon_key", CARDS)
    def test_without_commit_base_skill_fails(self, game, card_id, cls, skill, icon_key):
        game.register_card_data(make_skill_data(id=card_id, skill_icons={icon_key: 4}))
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test("test_investigator", skill, 4)
        assert not result.success  # 3 vs 4
