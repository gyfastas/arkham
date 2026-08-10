"""Tests for Quick Study (Level 2).

官方：[快速]将你的1个线索放在所在地点上，并消耗一目十行：这次技能
检定你的技能值+3。
"""

import pytest

from backend.cards.seeker.quick_study_lv2 import QuickStudy
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test_quick_study")
    g.chaos_bag.seed(42)
    g.chaos_bag.tokens = [ChaosTokenType.ZERO]

    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a")
    g.register_card_data(loc_data)
    g.add_investigator("player", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_data, clues=1)

    g.register_card_data(make_asset_data(
        id="quick_study_lv2", name="Quick Study", cost=2, traits=["talent"]))
    inst = CardInstance(
        instance_id="inst_qs", card_id="quick_study_lv2",
        owner_id="player", controller_id="player",
    )
    g.state.cards_in_play["inst_qs"] = inst
    inv = g.state.get_investigator("player")
    inv.play_area.append("inst_qs")
    inv.clues = 2

    impl = QuickStudy("inst_qs")
    impl.register(g.event_bus, "inst_qs")
    return g, impl


class TestQuickStudy:
    def test_spend_clue_boosts_test_by_three(self, game):
        """放回1线索并消耗：本次检定+3（3+3=6过难度5）。"""
        g, impl = game
        inv = g.state.get_investigator("player")
        loc = g.state.get_location("loc_a")
        assert impl.spend(g.state, "player") is True
        assert inv.clues == 1
        assert loc.clues == 2
        assert g.state.get_card_instance("inst_qs").exhausted is True

        result = g.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.INTELLECT,
            difficulty=5,
        )
        assert result.success is True
        sources = result.extra.get("skill_bonus_sources", [])
        assert any(s["reason"] == "quick_study_boost" and s["delta"] == 3
                   for s in sources)

    def test_spend_requires_clue(self, game):
        g, impl = game
        inv = g.state.get_investigator("player")
        inv.clues = 0
        assert impl.spend(g.state, "player") is False

    def test_spend_requires_ready(self, game):
        g, impl = game
        g.state.get_card_instance("inst_qs").exhausted = True
        assert impl.spend(g.state, "player") is False
