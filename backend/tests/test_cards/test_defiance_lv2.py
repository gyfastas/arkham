"""Tests for Defiance (Level 2). (04198)

投入本卡的检定：忽略所有 skull/cultist/tablet/elder_thing 符号的效果
（包括修正值）；不忽略 auto_fail。
"""

import pytest
from backend.cards.mystic.defiance_lv2 import Defiance
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_investigator_data, make_skill_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    state.investigators["inv1"] = inv
    state.card_database["defiance_lv2"] = make_skill_data(
        id="defiance_lv2", name="Defiance")
    impl = Defiance("impl_def")
    impl.register(bus, "impl_def")
    return state, bus, inv, impl


def _commit(state, bus, cards):
    bus.emit(EventContext(
        game_state=state, event=GameEvent.SKILL_TEST_COMMIT,
        investigator_id="inv1", skill_type=Skill.WILLPOWER,
        committed_cards=cards, amount=1,
    ))


def _token(state, bus, token, amount):
    ctx = EventContext(
        game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
        investigator_id="inv1", chaos_token=token, amount=amount,
    )
    bus.emit(ctx)
    return ctx


class TestDefiance:
    def test_ignores_skull_modifier_and_effect(self, setup):
        """投入后：skull 修正清零，符号被抑制（chaos_token 置 None）。"""
        state, bus, inv, impl = setup
        _commit(state, bus, ["defiance_lv2"])
        ctx = _token(state, bus, ChaosTokenType.SKULL, -2)
        assert ctx.amount == 0
        assert ctx.chaos_token is None
        assert ctx.extra["defiance_ignored"] == "skull"

    def test_ignores_tablet_and_elder_thing(self, setup):
        state, bus, inv, impl = setup
        _commit(state, bus, ["defiance_lv2"])
        for token in (ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING,
                      ChaosTokenType.CULTIST):
            ctx = _token(state, bus, token, -1)
            assert ctx.chaos_token is None
            assert ctx.amount == 0

    def test_does_not_ignore_auto_fail(self, setup):
        """auto_fail 不在卡面列表中。"""
        state, bus, inv, impl = setup
        _commit(state, bus, ["defiance_lv2"])
        ctx = _token(state, bus, ChaosTokenType.AUTO_FAIL, 0)
        assert ctx.chaos_token == ChaosTokenType.AUTO_FAIL

    def test_numbered_tokens_untouched(self, setup):
        state, bus, inv, impl = setup
        _commit(state, bus, ["defiance_lv2"])
        ctx = _token(state, bus, ChaosTokenType.MINUS_3, -3)
        assert ctx.amount == -3
        assert ctx.chaos_token == ChaosTokenType.MINUS_3

    def test_not_committed_no_effect(self, setup):
        state, bus, inv, impl = setup
        _commit(state, bus, ["guts_lv0"])
        ctx = _token(state, bus, ChaosTokenType.SKULL, -2)
        assert ctx.amount == -2
        assert ctx.chaos_token == ChaosTokenType.SKULL

    def test_cleared_after_test(self, setup):
        state, bus, inv, impl = setup
        _commit(state, bus, ["defiance_lv2"])
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1",
        ))
        ctx = _token(state, bus, ChaosTokenType.SKULL, -2)
        assert ctx.amount == -2
