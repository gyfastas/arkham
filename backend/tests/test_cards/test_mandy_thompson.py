"""Tests for Mandy Thompson investigator elder sign (reaction is an engine gap)."""

import pytest

from backend.cards.seeker.mandy_thompson import MandyThompson
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.tests.conftest import (
    make_investigator_data, make_location_data, make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test_mandy")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="mandy_thompson", name="Mandy Thompson", intellect=5)
    g.register_card_data(inv_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)

    # 顶部3张：2张无图标卡 + 1张带2智力图标的技能卡
    g.register_card_data(make_skill_data(
        id="sharp_mind", name="Sharp Mind", skill_icons={"intellect": 2},
    ))

    deck = ["plain_a", "sharp_mind", "plain_b", "plain_c", "plain_d", "plain_e"]
    g.add_investigator("mandy", inv_data, deck=deck, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)

    # 保证检定必揭示远古印记
    g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
    return g


@pytest.fixture
def impl(game):
    impl = MandyThompson("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


class TestMandyThompsonElderSign:
    def test_default_draws_top_card_of_three(self, game, impl):
        """远古印记：默认抽取牌堆顶3张中的第1张，并混洗牌堆。"""
        inv = game.state.get_investigator("mandy")
        result = game.skill_test_engine.run_test("mandy", Skill.INTELLECT, 2)

        assert result.token == ChaosTokenType.ELDER_SIGN
        assert "plain_a" in inv.hand
        assert "plain_a" not in inv.deck
        assert len(inv.deck) == 5  # 6 - 1

    def test_preset_commit_adds_icons_to_test(self, game, impl):
        """预设投入：被投卡牌的匹配图标加到本次检定上，检定结束后入弃牌堆。"""
        inv = game.state.get_investigator("mandy")
        game.state.scenario.vars["mandy_thompson_elder_sign"] = {
            "card_id": "sharp_mind", "mode": "commit",
        }

        # 智力5 + 2图标 = 7 ≥ 难度6 → 成功（无投入则 5 < 6 失败）
        result = game.skill_test_engine.run_test("mandy", Skill.INTELLECT, 6)

        assert result.success
        assert result.modified_skill == 7
        assert "sharp_mind" not in inv.deck
        assert "sharp_mind" not in inv.hand
        assert "sharp_mind" in inv.discard
        # 预设为一次性
        assert "mandy_thompson_elder_sign" not in game.state.scenario.vars

    def test_preset_commit_with_no_matching_icons_falls_back_to_draw(self, game, impl):
        """投入的卡牌无匹配图标时（"if able"不成立）退化为抽取。"""
        inv = game.state.get_investigator("mandy")
        game.state.scenario.vars["mandy_thompson_elder_sign"] = {
            "card_id": "plain_b", "mode": "commit",
        }
        result = game.skill_test_engine.run_test("mandy", Skill.INTELLECT, 2)

        assert "plain_b" in inv.hand
        assert result.modified_skill == 5

    def test_preset_draw_of_chosen_card(self, game, impl):
        """预设抽取顶部3张中的指定卡牌。"""
        inv = game.state.get_investigator("mandy")
        game.state.scenario.vars["mandy_thompson_elder_sign"] = {
            "card_id": "sharp_mind", "mode": "draw",
        }
        game.skill_test_engine.run_test("mandy", Skill.INTELLECT, 2)

        assert "sharp_mind" in inv.hand
        assert "sharp_mind" not in inv.deck

    def test_no_effect_for_other_investigators(self, game, impl):
        """其他调查员揭示远古印记不触发曼蒂的效果。"""
        other_data = make_investigator_data(id="other_inv", name="Other", intellect=3)
        game.register_card_data(other_data)
        game.add_investigator(
            "other", other_data, deck=["x", "y", "z"], starting_location="test_location",
        )
        inv = game.state.get_investigator("mandy")

        game.skill_test_engine.run_test("other", Skill.INTELLECT, 1)
        assert inv.deck == ["plain_a", "sharp_mind", "plain_b", "plain_c", "plain_d", "plain_e"]
        assert inv.hand == []

    def test_no_effect_for_other_tokens(self, game, impl):
        """非远古印记不触发。"""
        inv = game.state.get_investigator("mandy")
        _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="mandy", chaos_token=ChaosTokenType.ZERO,
            skill_type=Skill.INTELLECT,
        )
        assert inv.deck[0] == "plain_a"
        assert inv.hand == []
