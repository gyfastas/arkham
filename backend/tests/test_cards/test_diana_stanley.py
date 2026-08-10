"""Tests for Diana Stanley investigator ability."""

import pytest
from backend.cards.mystic.diana_stanley import DianaStanley, beneath_key
from backend.cards.mystic.ward_of_protection_lv0 import WardOfProtection
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import (
    CardType, ChaosTokenType, GameEvent, Skill,
)
from backend.models.state import CardData
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)


def _make_game():
    g = Game("test_diana")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="diana_stanley", name="Diana Stanley",
                                      willpower=1)
    g.register_card_data(inv_data)
    loc_data = make_location_data()
    g.register_card_data(loc_data)
    g.register_card_data(make_event_data(id="ward_of_protection_lv0", cost=1))
    g.register_card_data(CardData(
        id="treach_a", name="Treachery A", name_cn="诡计A",
        type=CardType.TREACHERY,
    ))

    g.add_investigator("diana", inv_data, deck=["filler"] * 15,
                       starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)
    return g


def _impl(g):
    return g.card_registry.active_instances["investigator_diana"]


def _register_ward(g, instance_id="w1"):
    ward = WardOfProtection(instance_id)
    ward.register(g.event_bus, instance_id)
    return ward


def _draw_treachery(g, investigator_id="diana"):
    g.event_bus.emit(EventContext(
        game_state=g.state,
        event=GameEvent.ENCOUNTER_CARD_DRAWN,
        investigator_id=investigator_id,
        extra={"card_id": "treach_a"},
    ))


class TestSetup:
    def test_setup_activates_impl(self):
        g = _make_game()
        g.setup()
        assert isinstance(_impl(g), DianaStanley)

    def test_dark_insight_added_to_opening_hand(self):
        """额外设置：起始手牌额外有1张黑暗洞察（5抽牌+黑暗洞察=6张）。"""
        g = _make_game()
        g.setup()
        inv = g.state.get_investigator("diana")
        assert len(inv.hand) == 6
        assert "dark_insight_lv0" in inv.hand


class TestWillpowerBonus:
    def test_willpower_per_card_beneath(self):
        """底下每有1张卡牌 +1意志。"""
        g = _make_game()
        g.setup()
        g.state.scenario.vars[beneath_key("diana")] = ["c1", "c2"]

        assert g.preview_skill_bonuses("diana") == {"willpower": 2}

        g.chaos_bag.tokens = [ChaosTokenType.ZERO]
        result = g.skill_test_engine.run_test(
            investigator_id="diana", skill_type=Skill.WILLPOWER, difficulty=3,
        )
        assert result.modified_skill == 3  # 1 + 2
        assert result.success is True


class TestCancelReaction:
    def test_owned_cancel_card_goes_beneath(self):
        """黛安娜的守护结界取消诡计后：结界置于她底下，抽1牌得1资源。"""
        g = _make_game()
        g.setup()
        _register_ward(g)
        inv = g.state.get_investigator("diana")
        inv.hand.append("ward_of_protection_lv0")
        inv.resources = 5
        hand_before = len(inv.hand)

        _draw_treachery(g)

        # 守护结界结算：支付1资源、入弃牌堆、受1恐惧
        assert g.state.scenario.vars["cancelled_encounter"] == "treach_a"
        assert inv.horror == 1
        # 黛安娜反应：置于她底下（从弃牌堆移走）、抽1牌、得1资源
        beneath = g.state.scenario.vars[beneath_key("diana")]
        assert beneath == ["ward_of_protection_lv0"]
        assert "ward_of_protection_lv0" not in inv.discard
        assert "ward_of_protection_lv0" not in inv.hand
        assert len(inv.hand) == hand_before  # -结界 +抽1
        assert inv.resources == 5  # -1（结界费用）+1（黛安娜）

    def test_other_investigators_cancel_not_collected(self):
        """其他调查员拥有的取消卡不会置于黛安娜底下。"""
        g = _make_game()
        other_data = make_investigator_data(id="other_inv", name="Other")
        g.register_card_data(other_data)
        g.add_investigator("other", other_data, deck=["filler"] * 10,
                           starting_location="test_location")
        g.setup()
        _register_ward(g)
        other = g.state.get_investigator("other")
        other.hand.append("ward_of_protection_lv0")
        other.resources = 5

        _draw_treachery(g, investigator_id="other")

        assert g.state.scenario.vars["cancelled_encounter"] == "treach_a"
        assert beneath_key("diana") not in g.state.scenario.vars \
            or not g.state.scenario.vars[beneath_key("diana")]
        assert "ward_of_protection_lv0" in other.discard

    def test_limit_once_per_phase(self):
        """每阶段限1次；新阶段重置。"""
        g = _make_game()
        g.setup()
        impl = _impl(g)
        inv = g.state.get_investigator("diana")
        inv.discard.append("cx")
        assert impl.notify_cancellation(g.state, "cx") is True

        inv.discard.append("cy")
        assert impl.notify_cancellation(g.state, "cy") is False  # 本阶段已用

        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.INVESTIGATION_PHASE_BEGINS,
        ))
        assert impl.notify_cancellation(g.state, "cy") is True
        assert g.state.scenario.vars[beneath_key("diana")] == ["cx", "cy"]

    def test_beneath_cap_5(self):
        """底下满5张后不再放置。"""
        g = _make_game()
        g.setup()
        impl = _impl(g)
        inv = g.state.get_investigator("diana")
        g.state.scenario.vars[beneath_key("diana")] = ["a", "b", "c", "d", "e"]
        inv.discard.append("cx")
        resources_before = inv.resources

        assert impl.notify_cancellation(g.state, "cx") is False
        assert inv.resources == resources_before
        assert len(g.state.scenario.vars[beneath_key("diana")]) == 5

    def test_notify_requires_ownership(self):
        """显式通报：归属校验（手牌/弃牌堆或 owner_id）。"""
        g = _make_game()
        g.setup()
        impl = _impl(g)
        # 不在手牌/弃牌堆且未声明归属
        assert impl.notify_cancellation(g.state, "ghost_card") is False
        # owner_id 显式声明为黛安娜
        assert impl.notify_cancellation(
            g.state, "ghost_card", owner_id="diana") is True
        assert g.state.scenario.vars[beneath_key("diana")] == ["ghost_card"]


class TestElderSign:
    def test_elder_sign_returns_first_card_beneath(self):
        """远古印记：+2，缺省将她底下第一张卡加入手牌。"""
        g = _make_game()
        g.setup()
        inv = g.state.get_investigator("diana")
        g.state.scenario.vars[beneath_key("diana")] = ["cx", "cy"]
        hand_before = len(inv.hand)

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = g.skill_test_engine.run_test(
            investigator_id="diana", skill_type=Skill.INTELLECT, difficulty=99,
        )
        assert result.token_modifier == 2
        assert "cx" in inv.hand
        assert g.state.scenario.vars[beneath_key("diana")] == ["cy"]
        assert len(inv.hand) == hand_before + 1

    def test_elder_sign_preset_choice(self):
        """预设选择她底下的指定卡牌。"""
        g = _make_game()
        g.setup()
        inv = g.state.get_investigator("diana")
        g.state.scenario.vars[beneath_key("diana")] = ["cx", "cy"]
        g.state.scenario.vars["diana_stanley_beneath_choice"] = "cy"

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        g.skill_test_engine.run_test(
            investigator_id="diana", skill_type=Skill.INTELLECT, difficulty=99,
        )
        assert "cy" in inv.hand
        assert g.state.scenario.vars[beneath_key("diana")] == ["cx"]

    def test_elder_sign_empty_beneath(self):
        """底下无卡：仅+2。"""
        g = _make_game()
        g.setup()
        inv = g.state.get_investigator("diana")
        hand_before = len(inv.hand)

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = g.skill_test_engine.run_test(
            investigator_id="diana", skill_type=Skill.INTELLECT, difficulty=99,
        )
        assert result.token_modifier == 2
        assert len(inv.hand) == hand_before
