"""Tests for Sure Gamble (Level 3)."""

import pytest
from backend.cards.rogue.sure_gamble_lv3 import SureGamble
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import ChaosTokenType, GameEvent, Skill
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_event_data, make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data

    sg_data = make_event_data(id="sure_gamble_lv3", cost=2)
    state.card_database["sure_gamble_lv3"] = sg_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
        hand=["sure_gamble_lv3"],
    )
    inv.resources = 5
    state.investigators["inv1"] = inv

    impl = SureGamble("sg_inst")
    impl.register(bus, "sg_inst")
    return state, bus, inv, impl


def _token_ctx(state, token, amount):
    return EventContext(
        game_state=state,
        event=GameEvent.CHAOS_TOKEN_RESOLVED,
        investigator_id="inv1",
        chaos_token=token,
        amount=amount,
        skill_type=Skill.COMBAT,
        difficulty=3,
    )


class TestSureGamble:
    def test_card_id(self):
        """Sure Gamble has correct card_id."""
        assert SureGamble.card_id == "sure_gamble_lv3"

    def test_flips_negative_token(self, setup):
        """A -2 token is switched to +2; the card is played from hand."""
        state, bus, inv, impl = setup

        ctx = _token_ctx(state, ChaosTokenType.MINUS_2, -2)
        bus.emit(ctx)

        assert ctx.amount == 2
        assert ctx.extra["sure_gamble_flipped"] is True
        assert "sure_gamble_lv3" not in inv.hand
        assert "sure_gamble_lv3" in inv.discard
        assert inv.resources == 3  # paid 2

    def test_no_trigger_on_positive_token(self, setup):
        state, bus, inv, impl = setup

        ctx = _token_ctx(state, ChaosTokenType.PLUS_1, 1)
        bus.emit(ctx)

        assert ctx.amount == 1
        assert "sure_gamble_lv3" in inv.hand
        assert inv.resources == 5

    def test_no_trigger_on_auto_fail(self, setup):
        """Auto-fail has no numeric modifier to flip."""
        state, bus, inv, impl = setup

        ctx = _token_ctx(state, ChaosTokenType.AUTO_FAIL, 0)
        bus.emit(ctx)

        assert "sure_gamble_lv3" in inv.hand
        assert inv.resources == 5

    def test_no_trigger_without_resources(self, setup):
        state, bus, inv, impl = setup
        inv.resources = 1

        ctx = _token_ctx(state, ChaosTokenType.MINUS_1, -1)
        bus.emit(ctx)

        assert ctx.amount == -1
        assert "sure_gamble_lv3" in inv.hand

    def test_no_trigger_when_not_in_hand(self, setup):
        state, bus, inv, impl = setup
        inv.hand = []

        ctx = _token_ctx(state, ChaosTokenType.MINUS_1, -1)
        bus.emit(ctx)

        assert ctx.amount == -1
