"""Tests for Shrewd Analysis (Level 0) / Studious (Level 3).

shrewd_analysis_lv0：永久。升级(未鉴定)/(未翻译)卡牌时可免费多升级1张，
两个升级版本随机选取（战役/构筑层规则，见实现说明）。
studious_lv3：永久。起始手牌额外1张（会话层开局调用，见实现说明）。
"""

import random

import pytest

from backend.cards.seeker.shrewd_analysis_lv0 import ShrewdAnalysis
from backend.cards.seeker.studious_lv3 import Studious
from backend.engine.game import Game
from backend.tests.conftest import (
    make_investigator_data, make_location_data,
)


class TestShrewdAnalysis:
    def test_choose_upgrade_pair_picks_two_distinct(self):
        """从4个可选升级版本中随机选2个不同版本。"""
        options = ["strange_solution_acidic", "strange_solution_icy",
                   "strange_solution_freezing", "strange_solution_restoring"]
        rng = random.Random(7)
        picked = ShrewdAnalysis.choose_upgrade_pair(options, rng=rng)
        assert len(picked) == 2
        assert len(set(picked)) == 2
        assert all(p in options for p in picked)

    def test_choose_upgrade_pair_with_fewer_options(self):
        """选项不足2个时全取。"""
        assert ShrewdAnalysis.choose_upgrade_pair(["only_one"]) == ["only_one"]

    def test_subtitle_detection(self):
        assert ShrewdAnalysis.is_upgradeable_subtitle("(Unidentified)") is True
        assert ShrewdAnalysis.is_upgradeable_subtitle("(Untranslated)") is True
        assert ShrewdAnalysis.is_upgradeable_subtitle("Finder of Facts") is False
        assert ShrewdAnalysis.is_upgradeable_subtitle(None) is False


class TestStudious:
    def test_opening_hand_extra_card(self):
        """开局应用：起始手牌额外抽1张。"""
        g = Game("test_studious")
        inv_data = make_investigator_data()
        g.register_card_data(inv_data)
        loc_data = make_location_data(id="loc_a")
        g.register_card_data(loc_data)
        g.add_investigator(
            "player", inv_data,
            deck=["card_a", "card_b"], starting_location="loc_a")
        g.add_location("loc_a", loc_data, clues=0)
        inv = g.state.get_investigator("player")

        impl = Studious("inst_studious")
        assert Studious.opening_hand_bonus() == 1
        assert impl.apply_opening_hand(g.state, "player") is True
        assert inv.hand == ["card_a"]
        assert inv.deck == ["card_b"]
