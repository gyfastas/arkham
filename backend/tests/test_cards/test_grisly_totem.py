"""Tests for Grisly Totem (Level 3)."""

import pytest
from backend.cards.seeker.grisly_totem_lv3 import GrislyTotem
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
    totem = make_asset_data(id="grisly_totem_lv3", name="Grisly Totem", cost=3)
    g.register_card_data(totem)
    skill = make_skill_data(id="test_skill_int", name="Test Skill",
                            skill_icons={"intellect": 1})
    g.register_card_data(skill)

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=0)

    inst = CardInstance(
        instance_id="totem_1", card_id="grisly_totem_lv3",
        owner_id="inv1", controller_id="inv1",
    )
    g.state.cards_in_play["totem_1"] = inst
    inv = g.state.get_investigator("inv1")
    inv.play_area.append("totem_1")
    g.card_registry.register_class(GrislyTotem)
    impl = GrislyTotem("totem_1")
    impl.register(g.event_bus, "totem_1")
    return g


class TestGrislyTotem:
    def test_extra_icon_and_draw_on_success(self, game):
        """投入卡额外+1图标（3+1+1=5 对难度4 成功），成功后抽1张。"""
        inv = game.state.get_investigator("inv1")
        inv.hand.append("test_skill_int")
        inv.deck = ["w1"]
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inst = game.state.get_card_instance("totem_1")

        result = game.skill_test_engine.run_test(
            "inv1", Skill.INTELLECT, difficulty=4,
            committed_card_ids=["test_skill_int"],
        )
        assert result.committed_icons == 2  # 1原图标 + 1图腾
        assert result.success is True
        assert inst.exhausted is True
        assert inv.hand == ["w1"]  # 成功抽1张

    def test_no_draw_on_failure(self, game):
        """检定失败：不抽牌（图标仍加）。"""
        inv = game.state.get_investigator("inv1")
        inv.hand.append("test_skill_int")
        inv.deck = ["w1"]
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_3]

        result = game.skill_test_engine.run_test(
            "inv1", Skill.INTELLECT, difficulty=4,
            committed_card_ids=["test_skill_int"],
        )
        # 3 + 2图标 - 3 = 2 < 4 失败
        assert result.success is False
        assert inv.hand == []

    def test_no_trigger_without_commit(self, game):
        """未投入卡牌：图腾不消耗。"""
        inv = game.state.get_investigator("inv1")
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        inst = game.state.get_card_instance("totem_1")

        game.skill_test_engine.run_test("inv1", Skill.INTELLECT, difficulty=2)
        assert inst.exhausted is False
