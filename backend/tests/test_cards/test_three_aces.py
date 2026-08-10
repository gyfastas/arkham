"""Tests for Three Aces (Level 1)."""

import pytest

from backend.cards.rogue.three_aces_lv1 import ThreeAces
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_investigator_data

THREE = ["three_aces_lv1"] * 3


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
        deck=["c1", "c2", "c3", "c4"],
    )
    inv.resources = 1
    state.investigators["inv1"] = inv
    # 引擎会为每张投入卡激活一个临时实现实例；此处注册3个模拟
    impls = []
    for i in range(3):
        impl = ThreeAces(f"aces_{i}")
        impl.register(bus, f"aces_{i}")
        impls.append(impl)
    return state, bus, inv


def _commit(bus, state, cards):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.SKILL_TEST_COMMIT,
        investigator_id="inv1",
        skill_type=Skill.COMBAT,
        difficulty=4,
        committed_cards=list(cards),
        amount=len(cards),
    )
    bus.emit(ctx)
    return ctx


class TestThreeAces:
    def test_three_copies_auto_success_and_reward(self, setup):
        state, bus, inv = setup
        ctx = _commit(bus, state, THREE)
        assert ctx.difficulty == 0
        assert ctx.extra["three_aces_auto_success"] is True

        # 引擎仍揭示标记；auto_fail 被取消
        tok = EventContext(
            game_state=state,
            event=GameEvent.CHAOS_TOKEN_RESOLVED,
            investigator_id="inv1",
            chaos_token=ChaosTokenType.AUTO_FAIL,
            amount=0,
            skill_type=Skill.COMBAT,
            difficulty=0,
        )
        bus.emit(tok)
        assert tok.extra.get("cancel_auto_fail") is True

        ok = EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            success=True,
            modified_skill=5,
            difficulty=0,
        )
        bus.emit(ok)
        assert ok.extra["three_aces_rewarded"] is True
        assert ok.extra["three_aces_drawn"] == 3
        assert inv.hand == ["c1", "c2", "c3"]
        assert inv.deck == ["c4"]
        assert inv.resources == 4  # 1 + 3

    def test_two_copies_no_effect(self, setup):
        state, bus, inv = setup
        ctx = _commit(bus, state, THREE[:2])
        assert ctx.difficulty == 4
        assert "three_aces_auto_success" not in ctx.extra

        ok = EventContext(
            game_state=state,
            event=GameEvent.SKILL_TEST_SUCCESSFUL,
            investigator_id="inv1",
            skill_type=Skill.COMBAT,
            success=True,
            modified_skill=5,
            difficulty=4,
        )
        bus.emit(ok)
        assert "three_aces_rewarded" not in ok.extra
        assert inv.hand == []
