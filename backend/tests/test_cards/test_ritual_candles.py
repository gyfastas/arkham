"""Tests for Ritual Candles (Level 0). (02029)

[reaction] 你进行的检定揭示 skull/cultist/tablet/elder_thing 后：本次检定+1技能值。
"""

import pytest
from backend.cards.mystic.ritual_candles_lv0 import RitualCandles
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_asset_data, make_investigator_data


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

    state.card_database["ritual_candles_lv0"] = make_asset_data(
        id="ritual_candles_lv0", name="Ritual Candles", traits=["item"],
    )
    inst = CardInstance(
        instance_id="inst_rc", card_id="ritual_candles_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["inst_rc"] = inst
    inv.play_area.append("inst_rc")

    impl = RitualCandles("inst_rc")
    impl.register(bus, "inst_rc")
    return state, bus, inv, inst, impl


def _token(state, bus, token, investigator_id="inv1"):
    bus.emit(EventContext(
        game_state=state, event=GameEvent.CHAOS_TOKEN_RESOLVED,
        investigator_id=investigator_id, chaos_token=token,
    ))


def _skill_value(state, bus, investigator_id="inv1", amount=3):
    ctx = EventContext(
        game_state=state, event=GameEvent.SKILL_VALUE_DETERMINED,
        investigator_id=investigator_id, skill_type=Skill.WILLPOWER,
        amount=amount,
    )
    bus.emit(ctx)
    return ctx


class TestRitualCandles:
    @pytest.mark.parametrize("token", [
        ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
        ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING,
    ])
    def test_plus_one_on_symbol_tokens(self, setup, token):
        state, bus, inv, inst, impl = setup
        _token(state, bus, token)
        ctx = _skill_value(state, bus)
        assert ctx.amount == 4

    @pytest.mark.parametrize("token", [
        ChaosTokenType.AUTO_FAIL, ChaosTokenType.MINUS_2,
        ChaosTokenType.ELDER_SIGN, ChaosTokenType.ZERO,
    ])
    def test_no_bonus_on_other_tokens(self, setup, token):
        """auto_fail 不在官方四符号之列，数值标记也不触发。"""
        state, bus, inv, inst, impl = setup
        _token(state, bus, token)
        ctx = _skill_value(state, bus)
        assert ctx.amount == 3

    def test_only_owner_tests_trigger(self, setup):
        """仅控制者自己进行的检定触发。"""
        state, bus, inv, inst, impl = setup
        other_data = make_investigator_data(id="other_inv", name="Other")
        state.card_database[other_data.id] = other_data
        state.investigators["inv2"] = InvestigatorState(
            investigator_id="inv2", card_data=other_data, location_id="loc1",
        )
        _token(state, bus, ChaosTokenType.SKULL, investigator_id="inv2")
        assert _skill_value(state, bus, investigator_id="inv2").amount == 3
        # 其他人的检定也不消耗/武装蜡烛
        assert _skill_value(state, bus, investigator_id="inv1").amount == 3

    def test_cleared_after_test_ends(self, setup):
        state, bus, inv, inst, impl = setup
        _token(state, bus, ChaosTokenType.SKULL)
        bus.emit(EventContext(
            game_state=state, event=GameEvent.SKILL_TEST_ENDS,
            investigator_id="inv1",
        ))
        assert _skill_value(state, bus).amount == 3
