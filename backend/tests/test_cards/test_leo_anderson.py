"""Tests for Leo Anderson investigator ability."""

import pytest
from backend.cards.guardian.leo_anderson import LeoAnderson
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)

FILLERS = [f"filler_{i}" for i in range(10)]


def _make_game(deck=None):
    g = Game("test_leo")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="leo_anderson", name="Leo Anderson")
    g.register_card_data(inv_data)
    loc_data = make_location_data()
    g.register_card_data(loc_data)

    g.register_card_data(make_asset_data(id="ally_a", cost=3, traits=["ally"]))
    g.register_card_data(make_asset_data(id="ally_b", cost=2, traits=["ally"]))
    g.register_card_data(make_asset_data(id="tool_a", cost=2))  # 非盟友

    g.add_investigator("leo", inv_data, deck=deck or list(FILLERS),
                       starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)
    return g


def _impl(g):
    return g.card_registry.active_instances["investigator_leo"]


def _turn_begins(g):
    g.event_bus.emit(EventContext(
        game_state=g.state,
        event=GameEvent.INVESTIGATOR_TURN_BEGINS,
        investigator_id="leo",
    ))


class TestSetupActivation:
    def test_setup_activates_impl(self):
        g = _make_game()
        g.setup()
        assert isinstance(_impl(g), LeoAnderson)


class TestPlayAllyReaction:
    def test_play_ally_at_reduced_cost(self):
        """回合开始后：打出盟友费用-1，不扣行动。"""
        g = _make_game()
        g.setup()
        impl = _impl(g)
        inv = g.state.get_investigator("leo")
        inv.hand.append("ally_a")
        inv.resources = 5
        inv.actions_remaining = 3

        _turn_begins(g)
        assert impl.activate_play_ally(g, "leo", "ally_a") is True

        assert "ally_a" not in inv.hand
        assert inv.resources == 3  # 3费-1=2
        assert inv.actions_remaining == 3  # 响应式打出不扣行动
        assert len(inv.play_area) == 1
        inst = g.state.get_card_instance(inv.play_area[0])
        assert inst is not None and inst.card_id == "ally_a"

    def test_window_closes_after_use_and_turn_end(self):
        """窗口打出一次后关闭；回合结束也关闭。"""
        g = _make_game()
        g.setup()
        impl = _impl(g)
        inv = g.state.get_investigator("leo")
        inv.hand.extend(["ally_a", "ally_b"])

        _turn_begins(g)
        assert impl.activate_play_ally(g, "leo", "ally_a") is True
        # 同一回合不能再触发
        assert impl.activate_play_ally(g, "leo", "ally_b") is False

        _turn_begins(g)
        g.event_bus.emit(EventContext(
            game_state=g.state,
            event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="leo",
        ))
        assert impl.activate_play_ally(g, "leo", "ally_b") is False

    def test_no_window_without_turn_begin(self):
        """未经过回合开始时不可发动。"""
        g = _make_game()
        g.setup()
        impl = _impl(g)
        inv = g.state.get_investigator("leo")
        inv.hand.append("ally_a")
        assert impl.activate_play_ally(g, "leo", "ally_a") is False

    def test_rejects_non_ally_and_insufficient_resources(self):
        """只能打盟友；资源不足（减费后）不可打出。"""
        g = _make_game()
        g.setup()
        impl = _impl(g)
        inv = g.state.get_investigator("leo")
        inv.hand.extend(["tool_a", "ally_a"])

        _turn_begins(g)
        assert impl.activate_play_ally(g, "leo", "tool_a") is False

        inv.resources = 1  # ally_a 减费后需2
        assert impl.activate_play_ally(g, "leo", "ally_a") is False

    def test_default_picks_first_ally_in_hand(self):
        """缺省自动取手牌中第一张盟友。"""
        g = _make_game()
        g.setup()
        impl = _impl(g)
        inv = g.state.get_investigator("leo")
        inv.hand.extend(["tool_a", "ally_b"])

        _turn_begins(g)
        assert impl.activate_play_ally(g, "leo") is True
        inst = g.state.get_card_instance(inv.play_area[0])
        assert inst.card_id == "ally_b"


class TestElderSign:
    def test_elder_sign_draws_ally_from_top3(self):
        """远古印记：+2，抽取牌堆顶3张中的第一张盟友并混洗。"""
        # setup 抽5张后，牌堆顶3张为 tool_a / ally_a / ally_b
        deck = FILLERS[:5] + ["tool_a", "ally_a", "ally_b"] + FILLERS[5:]
        g = _make_game(deck)
        g.setup()
        inv = g.state.get_investigator("leo")
        deck_before = len(inv.deck)

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = g.skill_test_engine.run_test(
            investigator_id="leo", skill_type=Skill.COMBAT, difficulty=99,
        )
        assert result.token_modifier == 2
        assert "ally_a" in inv.hand
        assert "ally_a" not in inv.deck
        assert len(inv.deck) == deck_before - 1  # 抽1张后混洗

    def test_elder_sign_no_ally_in_top3(self):
        """顶3张无盟友：只有+2并混洗，不抽牌。"""
        deck = FILLERS[:5] + ["tool_a"] * 3 + ["ally_a"] + FILLERS[5:]
        g = _make_game(deck)
        g.setup()
        inv = g.state.get_investigator("leo")
        hand_before = len(inv.hand)
        deck_set_before = set(inv.deck)

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = g.skill_test_engine.run_test(
            investigator_id="leo", skill_type=Skill.COMBAT, difficulty=99,
        )
        assert result.token_modifier == 2
        assert len(inv.hand) == hand_before
        assert set(inv.deck) == deck_set_before  # 混洗不换牌

    def test_other_token_no_effect(self):
        """非远古印记不触发。"""
        g = _make_game()
        g.setup()
        g.chaos_bag.tokens = [ChaosTokenType.SKULL]
        # skull 数值由剧本设定，此处无剧本实现 → 0
        result = g.skill_test_engine.run_test(
            investigator_id="leo", skill_type=Skill.COMBAT, difficulty=99,
        )
        assert result.token_modifier == 0
