"""Tests for Guided by the Unseen (Level 3)."""

import pytest
from backend.cards.seeker.guided_by_the_unseen_lv3 import GuidedByTheUnseen
from backend.engine.game import Game
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, Skill
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data, make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag = ChaosBag()
    g.chaos_bag.seed(42)
    g.skill_test_engine.chaos_bag = g.chaos_bag

    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)
    loc_data = make_location_data()
    g.register_card_data(loc_data)
    g.register_card_data(make_asset_data(
        id="guided_by_the_unseen_lv3", name="Guided by the Unseen", cost=2))
    g.register_card_data(make_skill_data(
        id="deck_skill", name="Deck Skill", skill_icons={"intellect": 2}))
    g.register_card_data(make_skill_data(
        id="deck_blank", name="Blank", skill_icons={"combat": 1}))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=0)

    inst = CardInstance(
        instance_id="gbu_1", card_id="guided_by_the_unseen_lv3",
        owner_id="inv1", controller_id="inv1",
    )
    inst.uses = {"secretss": 4}  # 生产数据的双 s 键
    g.state.cards_in_play["gbu_1"] = inst
    inv = g.state.get_investigator("inv1")
    inv.play_area.append("gbu_1")
    impl = GuidedByTheUnseen("gbu_1")
    impl.register(g.event_bus, "gbu_1")
    return g


class TestGuidedByTheUnseen:
    def test_commit_from_top_of_deck(self, game):
        """顶3张内有匹配卡：自动花1秘密投入（+2图标），检定结束入弃牌堆。"""
        inv = game.state.get_investigator("inv1")
        inv.deck = ["deck_blank", "deck_skill", "rest_1", "rest_2"]
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inst = game.state.get_card_instance("gbu_1")

        result = game.skill_test_engine.run_test(
            "inv1", Skill.INTELLECT, difficulty=5,
        )
        # 智力3 + 2图标 + 0 = 5 恰好成功
        assert result.committed_icons == 2
        assert result.success is True
        assert inst.uses["secretss"] == 3
        assert "deck_skill" in inv.discard
        assert "deck_skill" not in inv.deck

    def test_no_matching_card_no_secret_spent(self, game):
        """顶3张无可投入卡：不花秘密。"""
        inv = game.state.get_investigator("inv1")
        inv.deck = ["deck_blank", "deck_blank", "deck_blank", "deck_skill"]
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inst = game.state.get_card_instance("gbu_1")

        result = game.skill_test_engine.run_test(
            "inv1", Skill.INTELLECT, difficulty=5,
        )
        assert result.committed_icons == 0
        assert inst.uses["secretss"] == 4

    def test_limit_once_per_test(self, game):
        """每次检定限1次：同一检定不会重复投入。"""
        inv = game.state.get_investigator("inv1")
        inv.deck = ["deck_skill", "deck_skill", "deck_skill", "rest"]
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inst = game.state.get_card_instance("gbu_1")

        result = game.skill_test_engine.run_test(
            "inv1", Skill.INTELLECT, difficulty=5,
        )
        assert result.committed_icons == 2  # 只投入1张
        assert inst.uses["secretss"] == 3
