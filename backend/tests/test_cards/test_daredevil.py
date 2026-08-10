"""Tests for Daredevil (Level 2)."""

import pytest
from backend.cards.rogue.daredevil_lv2 import Daredevil
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, PlayerClass, Skill
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data, make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_skill_data(
        id="daredevil_lv2", name="Daredevil", card_class=PlayerClass.ROGUE,
        skill_icons={"wild": 1},
    ))
    g.register_card_data(make_skill_data(
        id="rogue_skill_x", name="Rogue Skill", card_class=PlayerClass.ROGUE,
        skill_icons={"combat": 2},
    ))
    g.register_card_data(make_skill_data(
        id="guardian_skill_x", name="Guardian Skill",
        card_class=PlayerClass.GUARDIAN, skill_icons={"combat": 2},
    ))
    g.register_card_data(make_asset_data(id="asset_x", name="Asset"))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(Daredevil)
    return g


class TestDaredevil:
    def test_reveal_and_commit_rogue_skill(self, game):
        """投入后揭示牌堆顶直至流浪者技能：将其投入（计图标），其余洗回。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["daredevil_lv2"]
        inv.deck = ["asset_x", "rogue_skill_x", "asset_x"]
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        result = game.skill_test_engine.run_test(
            "inv1", Skill.COMBAT, 10,
            committed_card_ids=["daredevil_lv2"],
        )
        # 基础3 + 虎口拔牙1(wild) + 揭示投入2 = 6
        assert result.committed_icons == 1 + 2
        assert result.modified_skill == 6
        # 其余揭示卡（第一张 asset_x）洗回牌堆
        assert "asset_x" in inv.deck
        assert len(inv.deck) == 2
        # 被揭示投入的是流浪者技能：检定结束后置入弃牌堆（来自牌堆）
        assert "rogue_skill_x" in inv.discard
        assert "rogue_skill_x" not in inv.deck

    def test_no_rogue_skill_in_deck(self, game):
        """牌堆无流浪者技能：全部洗回，无额外图标。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["daredevil_lv2"]
        inv.deck = ["asset_x", "guardian_skill_x"]
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        result = game.skill_test_engine.run_test(
            "inv1", Skill.COMBAT, 10,
            committed_card_ids=["daredevil_lv2"],
        )
        assert result.committed_icons == 1
        assert sorted(inv.deck) == ["asset_x", "guardian_skill_x"]

    def test_skips_non_rogue_skills(self, game):
        """守护者技能不算：继续揭示直到流浪者技能。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["daredevil_lv2"]
        inv.deck = ["guardian_skill_x", "rogue_skill_x"]
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        result = game.skill_test_engine.run_test(
            "inv1", Skill.COMBAT, 10,
            committed_card_ids=["daredevil_lv2"],
        )
        # 跳过守护者技能，投入流浪者技能（+2图标）
        assert result.committed_icons == 1 + 2
        assert "rogue_skill_x" in inv.discard
        assert "guardian_skill_x" in inv.deck
