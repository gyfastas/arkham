"""Tests for Amanda Sharpe investigator ability and elder sign."""

import pytest

from backend.cards.seeker.amanda_sharpe import AmandaSharpe
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.tests.conftest import (
    make_investigator_data, make_location_data, make_skill_data,
)


@pytest.fixture
def game():
    g = Game("test_amanda")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(
        id="amanda_sharpe", name="Amanda Sharpe",
        willpower=2, intellect=2, combat=2, agility=2,
    )
    g.register_card_data(inv_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)

    g.register_card_data(make_skill_data(
        id="deep_study", name="Deep Study", skill_icons={"intellect": 2},
    ))

    deck = [f"deck_{i}" for i in range(10)]
    g.add_investigator("amanda", inv_data, deck=deck, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)
    return g


@pytest.fixture
def impl(game):
    impl = AmandaSharpe("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


def _beneath(game):
    return game.state.scenario.vars.get("beneath_amanda", [])


class TestAmandaSharpePhaseBegins:
    def test_phase_begin_draws_cycles_and_places_beneath(self, game, impl):
        """调查阶段开始：抽1张牌，默认将手牌第1张置于其下。"""
        inv = game.state.get_investigator("amanda")
        inv.hand = ["hand_a", "hand_b"]

        _emit(game, GameEvent.INVESTIGATION_PHASE_BEGINS)

        assert _beneath(game) == ["hand_a"]
        assert inv.hand == ["hand_b", "deck_0"]
        assert inv.deck == [f"deck_{i}" for i in range(1, 10)]

    def test_phase_begin_discards_previous_beneath(self, game, impl):
        """调查阶段开始：先弃掉底下原有卡牌，再放置新卡。"""
        inv = game.state.get_investigator("amanda")
        inv.hand = ["hand_a"]
        game.state.scenario.vars["beneath_amanda"] = ["old_beneath"]

        _emit(game, GameEvent.INVESTIGATION_PHASE_BEGINS)

        assert "old_beneath" in inv.discard
        assert _beneath(game) == ["hand_a"]

    def test_phase_begin_place_preset(self, game, impl):
        """预设指定放置的手牌（一次性）。"""
        inv = game.state.get_investigator("amanda")
        inv.hand = ["hand_a", "hand_b"]
        game.state.scenario.vars["amanda_sharpe_place"] = "hand_b"

        _emit(game, GameEvent.INVESTIGATION_PHASE_BEGINS)

        assert _beneath(game) == ["hand_b"]
        assert "amanda_sharpe_place" not in game.state.scenario.vars

    def test_phase_begin_no_hand_no_place(self, game, impl):
        """手牌为空（且牌库抽空）时不放置。"""
        inv = game.state.get_investigator("amanda")
        inv.hand = []
        inv.deck = []

        _emit(game, GameEvent.INVESTIGATION_PHASE_BEGINS)
        assert _beneath(game) == []

    def test_no_effect_for_other_investigators(self, game, impl):
        """其他调查员不受阶段开始强制能力影响。"""
        other_data = make_investigator_data(id="other_inv", name="Other")
        game.register_card_data(other_data)
        other = game.add_investigator(
            "other", other_data, deck=["x", "y"], starting_location="test_location",
        )
        other.hand = ["hand_x"]

        _emit(game, GameEvent.INVESTIGATION_PHASE_BEGINS)
        assert other.hand == ["hand_x"]
        assert other.deck == ["x", "y"]
        assert "beneath_other" not in game.state.scenario.vars


class TestAmandaSharpeCommit:
    def test_beneath_card_icons_committed(self, game, impl):
        """技能检定：底下卡牌的匹配图标计入检定，卡牌留在底下不入弃牌堆。"""
        game.state.scenario.vars["beneath_amanda"] = ["deep_study"]
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        # 智力2 + 底下卡牌2图标 = 4
        result = game.skill_test_engine.run_test("amanda", Skill.INTELLECT, 4)

        assert result.committed_icons == 2
        assert result.modified_skill == 4
        assert result.success
        # 检定结束时不丢弃底下的卡牌
        assert _beneath(game) == ["deep_study"]
        assert "deep_study" not in game.state.get_investigator("amanda").discard

    def test_beneath_card_without_matching_icons_adds_nothing(self, game, impl):
        """底下卡牌无匹配图标时不加值。"""
        game.state.scenario.vars["beneath_amanda"] = ["deep_study"]
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        result = game.skill_test_engine.run_test("amanda", Skill.AGILITY, 2)
        assert result.committed_icons == 0
        assert result.modified_skill == 2

    def test_no_beneath_card_no_bonus(self, game, impl):
        """底下无卡牌时无加值。"""
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = game.skill_test_engine.run_test("amanda", Skill.INTELLECT, 2)
        assert result.committed_icons == 0


class TestAmandaSharpeElderSign:
    def test_elder_sign_doubles_beneath_icons(self, game, impl):
        """远古印记：底下卡牌的图标翻倍（投入2 + 翻倍2）。"""
        game.state.scenario.vars["beneath_amanda"] = ["deep_study"]
        game.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]

        # 智力2 + 投入2 + 翻倍2 = 6
        result = game.skill_test_engine.run_test("amanda", Skill.INTELLECT, 6)

        assert result.token == ChaosTokenType.ELDER_SIGN
        assert result.modified_skill == 6
        assert result.success
        assert _beneath(game) == ["deep_study"]

    def test_elder_sign_without_beneath_card_is_plus_zero(self, game, impl):
        """底下无卡牌时远古印记仅为+0。"""
        game.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = game.skill_test_engine.run_test("amanda", Skill.INTELLECT, 2)
        assert result.modified_skill == 2

    def test_no_double_for_other_investigators(self, game, impl):
        """其他调查员的检定不投入/不翻倍。"""
        game.state.scenario.vars["beneath_amanda"] = ["deep_study"]
        other_data = make_investigator_data(id="other_inv", name="Other", intellect=3)
        game.register_card_data(other_data)
        game.add_investigator("other", other_data, deck=[], starting_location="test_location")
        game.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]

        result = game.skill_test_engine.run_test("other", Skill.INTELLECT, 3)
        assert result.modified_skill == 3
