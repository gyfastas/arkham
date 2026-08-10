"""Tests for Eureka! (Level 0).

官方：如果本次技能检定成功，执行检定的调查员检索其牌库顶3张牌中的1张，
抽取之，并洗混其牌库。（实现简化为自动取第1张。）
"""

import pytest

from backend.cards.seeker.eureka_lv0 import Eureka
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, Skill
from backend.tests.conftest import (
    make_investigator_data, make_location_data, make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test_eureka")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)
    loc_data = make_location_data(id="loc_a")
    g.register_card_data(loc_data)
    g.add_investigator(
        "player", inv_data,
        deck=["card_a", "card_b", "card_c", "card_d"],
        starting_location="loc_a",
    )
    g.add_location("loc_a", loc_data, clues=0)

    g.register_card_data(make_skill_data(
        id="eureka_lv0",
        skill_icons={"willpower": 1, "intellect": 1, "agility": 1},
    ))
    g.card_registry.register_class(Eureka)
    inv = g.state.get_investigator("player")
    inv.hand = ["eureka_lv0"]
    return g


class TestEureka:
    def test_success_searches_top3_and_draws(self, game):
        """成功：从牌库顶3张中抽1张（自动第1张），牌库洗混。"""
        inv = game.state.get_investigator("player")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.INTELLECT,
            difficulty=3, committed_card_ids=["eureka_lv0"],
        )
        assert result.success is True
        assert "card_a" in inv.hand
        assert len(inv.deck) == 3  # 抽走1张
        assert result.extra.get("eureka_drawn") == "card_a"

    def test_failure_no_search(self, game):
        inv = game.state.get_investigator("player")
        game.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]
        result = game.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.INTELLECT,
            difficulty=3, committed_card_ids=["eureka_lv0"],
        )
        assert result.success is False
        assert "card_a" not in inv.hand
        assert len(inv.deck) == 4

    def test_not_committed_no_effect(self, game):
        inv = game.state.get_investigator("player")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test(
            investigator_id="player", skill_type=Skill.INTELLECT,
            difficulty=3,
        )
        assert result.success is True
        assert "card_a" not in inv.hand
