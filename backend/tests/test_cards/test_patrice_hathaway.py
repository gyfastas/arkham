"""Tests for Patrice Hathaway investigator ability and elder sign."""

import pytest

from backend.cards.survivor.patrice_hathaway import PatriceHathaway
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import CardData
from backend.models.enums import CardType, PlayerClass
from backend.tests.conftest import (
    make_investigator_data, make_location_data,
)


def _make_weakness_data(id="test_weakness"):
    return CardData(
        id=id, name="Test Weakness", name_cn="测试弱点",
        type=CardType.EVENT, card_class=PlayerClass.NEUTRAL,
        subtype="weakness",
    )


@pytest.fixture
def game():
    g = Game("test_patrice")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="patrice_hathaway", name="Patrice Hathaway")
    g.register_card_data(inv_data)

    loc_data = make_location_data()
    g.register_card_data(loc_data)

    g.register_card_data(_make_weakness_data())

    deck = [f"deck_{i}" for i in range(10)]
    g.add_investigator("patrice", inv_data, deck=deck, starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)
    return g


@pytest.fixture
def impl(game):
    impl = PatriceHathaway("test_instance")
    impl.register(game.event_bus, "test_instance")
    return impl


def _emit(game, event, **kwargs):
    ctx = EventContext(game_state=game.state, event=event, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


class TestPatriceHathawayUpkeep:
    def test_upkeep_replaces_draw_with_cycle_to_five(self, game, impl):
        """补给阶段：不抽1张，改为弃全部非弱点手牌并抽至5张（走引擎补给流程）。"""
        inv = game.state.get_investigator("patrice")
        inv.hand = ["hand_a", "hand_b"]
        inv.resources = 0

        game.upkeep_phase.resolve()

        assert inv.hand == ["deck_0", "deck_1", "deck_2", "deck_3", "deck_4"]
        assert sorted(inv.discard) == ["hand_a", "hand_b"]
        assert inv.deck == [f"deck_{i}" for i in range(5, 10)]
        assert inv.resources == 1  # 补给资源照常获得

    def test_upkeep_keeps_weakness_cards_in_hand(self, game, impl):
        """弱点手牌在补给阶段不被丢弃。"""
        inv = game.state.get_investigator("patrice")
        inv.hand = ["hand_a", "test_weakness"]

        game.upkeep_phase.resolve()

        assert "test_weakness" in inv.hand
        assert "hand_a" in inv.discard
        assert len(inv.hand) == 5  # 弱点 + 4张新牌

    def test_upkeep_draws_fewer_when_hand_partially_full(self, game, impl):
        """手牌全为弱点时仅抽补足5张。"""
        inv = game.state.get_investigator("patrice")
        inv.hand = ["test_weakness"]

        game.upkeep_phase.resolve()
        assert inv.hand == ["test_weakness", "deck_0", "deck_1", "deck_2", "deck_3"]

    def test_no_replacement_outside_upkeep(self, game, impl):
        """非补给阶段的抽牌不触发替换。"""
        from backend.models.enums import Phase
        game.state.scenario.current_phase = Phase.INVESTIGATION
        inv = game.state.get_investigator("patrice")
        inv.hand = ["hand_a"]

        _emit(game, GameEvent.CARD_DRAWN, investigator_id="patrice",
              extra={"card_id": "deck_0"})
        assert inv.hand == ["hand_a"]
        assert inv.discard == []

    def test_hand_size_reduced_by_three(self, game, impl):
        """手牌上限-3（补给阶段手牌检查通道）。"""
        ctx = _emit(
            game, GameEvent.UPKEEP_PHASE_BEGINS,
            investigator_id="patrice", amount=8,
        )
        assert ctx.amount == 5

    def test_hand_size_unaffected_for_others(self, game, impl):
        """其他调查员的手牌上限不受影响。"""
        other_data = make_investigator_data(id="other_inv", name="Other")
        game.register_card_data(other_data)
        game.add_investigator("other", other_data, deck=[], starting_location="test_location")

        ctx = _emit(
            game, GameEvent.UPKEEP_PHASE_BEGINS,
            investigator_id="other", amount=8,
        )
        assert ctx.amount == 8


class TestPatriceHathawayElderSign:
    def _run_elder_sign_test(self, game):
        game.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        return game.skill_test_engine.run_test("patrice", Skill.WILLPOWER, 2)

    def test_elder_sign_plus_one_and_shuffle_discard(self, game, impl):
        """远古印记：+1；检定结束后默认留下弃牌堆顶1张，其余混洗回牌堆。"""
        inv = game.state.get_investigator("patrice")
        inv.discard = ["old_a", "old_b", "old_c"]
        deck_before = list(inv.deck)

        result = self._run_elder_sign_test(game)

        assert result.success
        assert inv.discard == ["old_c"]  # 默认留下最近弃置的
        assert len(inv.deck) == len(deck_before) + 2
        assert "old_a" in inv.deck and "old_b" in inv.deck
        assert "old_c" not in inv.deck

    def test_elder_sign_keep_preset(self, game, impl):
        """预设指定留下的卡牌（一次性）。"""
        inv = game.state.get_investigator("patrice")
        inv.discard = ["old_a", "old_b", "old_c"]
        game.state.scenario.vars["patrice_hathaway_keep"] = "old_a"

        self._run_elder_sign_test(game)

        assert inv.discard == ["old_a"]
        assert "old_b" in inv.deck and "old_c" in inv.deck
        assert "patrice_hathaway_keep" not in game.state.scenario.vars

    def test_elder_sign_decline_preset(self, game, impl):
        """预设 decline：放弃混洗效果。"""
        inv = game.state.get_investigator("patrice")
        inv.discard = ["old_a", "old_b"]
        game.state.scenario.vars["patrice_hathaway_keep"] = "decline"

        self._run_elder_sign_test(game)
        assert inv.discard == ["old_a", "old_b"]

    def test_no_shuffle_without_elder_sign(self, game, impl):
        """未揭示远古印记的检定结束不混洗。"""
        inv = game.state.get_investigator("patrice")
        inv.discard = ["old_a", "old_b"]
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]

        game.skill_test_engine.run_test("patrice", Skill.WILLPOWER, 2)
        assert inv.discard == ["old_a", "old_b"]

    def test_elder_sign_modifier_is_plus_one(self, game, impl):
        """远古印记修正为+1（直接事件断言）。"""
        ctx = _emit(
            game, GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="patrice", chaos_token=ChaosTokenType.ELDER_SIGN,
            skill_type=Skill.WILLPOWER,
        )
        assert ctx.amount == 1
        # 清理武装状态，避免影响其他用例
        _emit(game, GameEvent.SKILL_TEST_ENDS, investigator_id="patrice")
