"""Tests for Sefina Rousseau investigator ability."""

import pytest
from backend.cards.neutral.stars_of_hyades_lv0 import beneath_key
from backend.cards.rogue.sefina_rousseau import SefinaRousseau
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, Skill
from backend.tests.conftest import (
    make_asset_data, make_event_data, make_investigator_data,
    make_location_data, make_skill_data,
)

# 13张开局牌：7事件 + 6非事件
EVENTS = ["evt_a", "evt_b", "evt_c", "evt_d", "evt_e", "evt_f", "evt_g"]
ASSETS = ["ast_a", "ast_b", "ast_c", "ast_d"]
SKILLS = ["skl_a", "skl_b"]


def _make_game(deck):
    g = Game("test_sefina")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="sefina_rousseau", name="Sefina Rousseau")
    g.register_card_data(inv_data)
    loc_data = make_location_data()
    g.register_card_data(loc_data)

    for cid in EVENTS:
        g.register_card_data(make_event_data(id=cid))
    for cid in ASSETS:
        g.register_card_data(make_asset_data(id=cid))
    for cid in SKILLS:
        g.register_card_data(make_skill_data(id=cid))

    g.add_investigator("sef", inv_data, deck=list(deck),
                       starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)
    return g


def _impl(game):
    return game.card_registry.active_instances["investigator_sef"]


class TestOpeningHand:
    def test_setup_draws_13_and_places_5_events_beneath(self):
        """开局强制能力：抽13张，前5张事件置于赛菲娜之下，保留8张。"""
        deck = EVENTS[:5] + ["evt_f", "ast_a", "ast_b", "skl_a",
                             "ast_c", "evt_g", "ast_d", "skl_b"] + ["extra"] * 5
        g = _make_game(deck)
        g.setup()

        inv = g.state.get_investigator("sef")
        beneath = g.state.scenario.vars[beneath_key("sef")]
        # 前5张事件按顺序置于赛菲娜之下
        assert beneath == ["evt_a", "evt_b", "evt_c", "evt_d", "evt_e"]
        # 保留8张起始手牌（13 - 5置于下方），无剩余弃牌
        assert len(inv.hand) == 8
        assert inv.discard == []
        assert set(inv.hand) == {"evt_f", "ast_a", "ast_b", "skl_a",
                                 "ast_c", "evt_g", "ast_d", "skl_b"}

    def test_setup_with_fewer_events_discards_rest(self):
        """事件不足5张时：全部事件置于下方，保留8张，弃掉其余。"""
        deck = ["evt_a", "ast_a", "ast_b", "skl_a", "evt_b",
                "ast_c", "ast_d", "skl_b"] + ["extra"] * 5
        g = _make_game(deck)
        for i in range(5):
            g.register_card_data(make_asset_data(id=f"extra{i}"))
        inv0 = g.state.get_investigator("sef")
        # 用已注册卡填充牌库尾部
        inv0.deck = deck[:8] + [f"extra{i}" for i in range(5)]
        g.setup()

        inv = g.state.get_investigator("sef")
        beneath = g.state.scenario.vars[beneath_key("sef")]
        assert beneath == ["evt_a", "evt_b"]
        assert len(inv.hand) == 8
        # 13 - 2（下方）- 8（保留）= 3 张弃置
        assert len(inv.discard) == 3

    def test_setup_activates_impl(self):
        """Game.setup() 自动激活赛菲娜的调查员实现。"""
        g = _make_game(EVENTS + ASSETS + SKILLS + ["extra"] * 5)
        g.setup()
        assert isinstance(_impl(g), SefinaRousseau)


class TestDrawBeneathAction:
    def test_activate_draw_beneath_costs_action(self):
        """[action]：花1行动，选择并抽取赛菲娜之下的一张事件卡。"""
        g = _make_game(EVENTS + ASSETS + SKILLS + ["extra"] * 5)
        g.setup()
        impl = _impl(g)
        inv = g.state.get_investigator("sef")
        inv.actions_remaining = 3

        assert impl.activate_draw_beneath(g.state, "sef", "evt_c")
        assert inv.actions_remaining == 2
        assert "evt_c" in inv.hand
        assert g.state.scenario.vars[beneath_key("sef")] == [
            "evt_a", "evt_b", "evt_d", "evt_e",
        ]

    def test_activate_draw_beneath_defaults_to_first_event(self):
        """缺省自动取赛菲娜之下的第一张事件。"""
        g = _make_game(EVENTS + ASSETS + SKILLS + ["extra"] * 5)
        g.setup()
        impl = _impl(g)
        inv = g.state.get_investigator("sef")

        assert impl.activate_draw_beneath(g.state, "sef")
        assert "evt_a" in inv.hand

    def test_activate_draw_beneath_validation(self):
        """非赛菲娜之下的卡/无行动/无事件时不可发动。"""
        g = _make_game(EVENTS + ASSETS + SKILLS + ["extra"] * 5)
        g.setup()
        impl = _impl(g)
        inv = g.state.get_investigator("sef")

        # 不在赛菲娜之下的卡
        assert not impl.activate_draw_beneath(g.state, "sef", "ast_a")
        # 无行动
        inv.actions_remaining = 0
        assert not impl.activate_draw_beneath(g.state, "sef")
        # 赛菲娜之下无事件
        inv.actions_remaining = 3
        g.state.scenario.vars[beneath_key("sef")] = []
        assert not impl.activate_draw_beneath(g.state, "sef")


class TestElderSign:
    def test_elder_sign_plus3_and_draws_event(self):
        """远古印记：+3，并抽取赛菲娜之下的第一张事件。"""
        g = _make_game(EVENTS + ASSETS + SKILLS + ["extra"] * 5)
        g.setup()
        inv = g.state.get_investigator("sef")
        hand_before = len(inv.hand)

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = g.skill_test_engine.run_test(
            investigator_id="sef", skill_type=Skill.AGILITY, difficulty=99,
        )
        assert result.token_modifier == 3
        assert "evt_a" in inv.hand
        assert len(inv.hand) == hand_before + 1
        assert g.state.scenario.vars[beneath_key("sef")] == [
            "evt_b", "evt_c", "evt_d", "evt_e",
        ]

    def test_elder_sign_plus3_only_when_beneath_empty(self):
        """赛菲娜之下无事件时远古印记只有 +3。"""
        g = _make_game(EVENTS + ASSETS + SKILLS + ["extra"] * 5)
        g.setup()
        g.state.scenario.vars[beneath_key("sef")] = []
        inv = g.state.get_investigator("sef")
        hand_before = len(inv.hand)

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = g.skill_test_engine.run_test(
            investigator_id="sef", skill_type=Skill.AGILITY, difficulty=99,
        )
        assert result.token_modifier == 3
        assert len(inv.hand) == hand_before
