"""Tests for Joe Diamond investigator ability (hunch deck)."""

import pytest
from backend.cards.seeker.joe_diamond import (
    JoeDiamond, hunch_deck_key, hunch_revealed_key,
)
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)

INSIGHTS = [f"ins_{i}" for i in range(12)]
FILLERS = [f"filler_{i}" for i in range(15)]


def _register_insights(g):
    for cid in INSIGHTS:
        cd = make_event_data(id=cid, cost=3)
        cd.traits = ["insight"]
        g.register_card_data(cd)
    unsolved = make_event_data(id="unsolved_case_lv0", cost=4)
    unsolved.traits = ["insight", "mystery"]
    unsolved.subtype = "weakness"
    g.register_card_data(unsolved)


def _make_game(deck):
    g = Game("test_joe")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(id="joe_diamond", name="Joe Diamond",
                                      intellect=4)
    g.register_card_data(inv_data)
    loc_data = make_location_data()
    g.register_card_data(loc_data)
    _register_insights(g)

    g.add_investigator("joe", inv_data, deck=list(deck),
                       starting_location="test_location")
    g.add_location("test_location", loc_data, clues=3)
    return g


def _impl(g):
    return g.card_registry.active_instances["investigator_joe"]


def _phase_begins(g):
    g.event_bus.emit(EventContext(
        game_state=g.state, event=GameEvent.INVESTIGATION_PHASE_BEGINS,
    ))


class TestSetupActivation:
    def test_setup_activates_impl(self):
        g = _make_game(FILLERS[:5] + INSIGHTS)
        g.setup()
        assert isinstance(_impl(g), JoeDiamond)


class TestHunchDeckFormation:
    def test_setup_forms_hunch_deck_of_11_insight_events(self):
        """setup 时自动组建直觉牌组：牌库中前11张洞察事件，移出牌库。"""
        deck = FILLERS[:5] + INSIGHTS + FILLERS[5:]
        g = _make_game(deck)
        g.setup()

        inv = g.state.get_investigator("joe")
        hunch = g.state.scenario.vars[hunch_deck_key("joe")]
        assert len(hunch) == 11
        assert set(hunch) == set(INSIGHTS[:11])
        # 移出牌库；第12张洞察事件留在牌库
        assert not set(hunch) & set(inv.deck)
        assert "ins_11" in inv.deck
        # 开局手牌为前5张非洞察牌
        assert inv.hand == FILLERS[:5]

    def test_unsolved_case_prioritized_into_hunch_deck(self):
        """悬案在牌库时优先进入直觉牌组。"""
        deck = FILLERS[:5] + INSIGHTS + ["unsolved_case_lv0"] + FILLERS[5:]
        g = _make_game(deck)
        g.setup()

        hunch = g.state.scenario.vars[hunch_deck_key("joe")]
        assert "unsolved_case_lv0" in hunch
        assert len(hunch) == 11

    def test_preset_hunch_deck_skips_auto_formation(self):
        """scenario.vars 预设直觉牌组时跳过自动组建。"""
        g = _make_game(FILLERS[:10])
        g.state.scenario.vars[hunch_deck_key("joe")] = ["ins_0", "ins_1"]
        g.setup()
        assert g.state.scenario.vars[hunch_deck_key("joe")] == ["ins_0", "ins_1"]


class TestRevealAndPlay:
    def test_phase_begins_reveals_top_card(self):
        """调查阶段开始：翻开直觉牌组顶部的牌。"""
        g = _make_game(FILLERS[:10])
        g.state.scenario.vars[hunch_deck_key("joe")] = ["ins_0", "ins_1"]
        g.setup()

        _phase_begins(g)
        vars_ = g.state.scenario.vars
        assert vars_[hunch_revealed_key("joe")] == "ins_0"
        assert vars_[hunch_deck_key("joe")] == ["ins_1"]

    def test_play_revealed_at_minus_2_cost(self):
        """以-2费用打出翻开的牌：扣资源扣行动，入弃牌堆。"""
        g = _make_game(FILLERS[:10])
        g.state.scenario.vars[hunch_deck_key("joe")] = ["ins_0", "ins_1"]
        g.setup()
        impl = _impl(g)
        inv = g.state.get_investigator("joe")
        inv.resources = 5
        inv.actions_remaining = 3
        _phase_begins(g)

        assert impl.activate_play_hunch(g, "joe") is True
        assert inv.resources == 4  # 3费-2=1
        assert inv.actions_remaining == 2
        assert "ins_0" in inv.discard
        assert g.state.scenario.vars[hunch_revealed_key("joe")] is None

    def test_play_revealed_validation(self):
        """资源不足/无翻开牌/无行动时不可打出。"""
        g = _make_game(FILLERS[:10])
        g.state.scenario.vars[hunch_deck_key("joe")] = ["ins_0"]
        g.setup()
        impl = _impl(g)
        inv = g.state.get_investigator("joe")

        assert impl.activate_play_hunch(g, "joe") is False  # 未翻开

        _phase_begins(g)
        inv.resources = 0  # 减费后需1
        assert impl.activate_play_hunch(g, "joe") is False

        inv.resources = 5
        inv.actions_remaining = 0
        assert impl.activate_play_hunch(g, "joe") is False

    def test_unplayed_card_shuffles_back_at_phase_end(self):
        """阶段结束未打出：混洗回直觉牌组。"""
        g = _make_game(FILLERS[:10])
        g.state.scenario.vars[hunch_deck_key("joe")] = ["ins_0", "ins_1"]
        g.setup()
        _phase_begins(g)

        g.event_bus.emit(EventContext(
            game_state=g.state, event=GameEvent.INVESTIGATION_PHASE_ENDS,
        ))
        vars_ = g.state.scenario.vars
        assert vars_[hunch_revealed_key("joe")] is None
        assert sorted(vars_[hunch_deck_key("joe")]) == ["ins_0", "ins_1"]


class TestElderSign:
    def test_elder_sign_moves_insight_from_discard_to_bottom(self):
        """远古印记：+1，弃牌堆第一张洞察事件移到直觉牌组底部。"""
        g = _make_game(FILLERS[:10])
        g.state.scenario.vars[hunch_deck_key("joe")] = ["ins_0"]
        g.setup()
        inv = g.state.get_investigator("joe")
        inv.discard.extend(["ins_5", "filler_0"])

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = g.skill_test_engine.run_test(
            investigator_id="joe", skill_type=Skill.INTELLECT, difficulty=99,
        )
        assert result.token_modifier == 1
        assert "ins_5" not in inv.discard
        # 底部 = 列表末尾
        assert g.state.scenario.vars[hunch_deck_key("joe")] == ["ins_0", "ins_5"]

    def test_elder_sign_preset_choice(self):
        """预设选择弃牌堆中的洞察事件。"""
        g = _make_game(FILLERS[:10])
        g.state.scenario.vars[hunch_deck_key("joe")] = []
        g.state.scenario.vars["joe_diamond_hunch_choice"] = "ins_7"
        g.setup()
        inv = g.state.get_investigator("joe")
        inv.discard.extend(["ins_5", "ins_7"])

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        g.skill_test_engine.run_test(
            investigator_id="joe", skill_type=Skill.INTELLECT, difficulty=99,
        )
        assert g.state.scenario.vars[hunch_deck_key("joe")] == ["ins_7"]
        assert inv.discard == ["ins_5"]

    def test_elder_sign_no_insight_in_discard(self):
        """弃牌堆无洞察事件：仅+1。"""
        g = _make_game(FILLERS[:10])
        g.state.scenario.vars[hunch_deck_key("joe")] = ["ins_0"]
        g.setup()
        inv = g.state.get_investigator("joe")
        inv.discard.append("filler_0")

        g.chaos_bag.tokens = [ChaosTokenType.ELDER_SIGN]
        result = g.skill_test_engine.run_test(
            investigator_id="joe", skill_type=Skill.INTELLECT, difficulty=99,
        )
        assert result.token_modifier == 1
        assert g.state.scenario.vars[hunch_deck_key("joe")] == ["ins_0"]
