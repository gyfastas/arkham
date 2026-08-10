"""Tests for 21 or Bust (Level 0)."""

import importlib

import pytest
from backend.engine.event_bus import EventBus, EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_investigator_data

_mod = importlib.import_module("backend.cards.rogue.21_or_bust_lv0")
TwentyOneOrBust = _mod.TwentyOneOrBust


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(42)

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    inv.resources = 5
    state.investigators["inv1"] = inv

    impl = TwentyOneOrBust("inst_21")
    impl.register(bus, "inst_21")
    impl.bind_chaos_bag(bag)
    return state, bus, inv, impl, bag


def _play(bus, state):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "21_or_bust_lv0"},
    )
    bus.emit(ctx)
    return ctx


class TestTwentyOneOrBust:
    def test_symbol_tokens_count_as_five_hit_20(self, setup):
        """Three skulls+tablet style 5s: 5,10,15,20 → stop at 20, gain 6."""
        state, bus, inv, impl, bag = setup
        bag.tokens = [ChaosTokenType.SKULL] * 3
        ctx = _play(bus, state)
        assert ctx.extra["21_or_bust"]["total"] == 20
        assert ctx.extra["21_or_bust"]["gained"] == 6
        assert inv.resources == 11
        assert len(ctx.extra["21_or_bust"]["tokens"]) == 4

    def test_auto_fail_counts_as_ten(self, setup):
        """auto_fail=10: 10 → 20, gain 6."""
        state, bus, inv, impl, bag = setup
        bag.tokens = [ChaosTokenType.AUTO_FAIL]
        ctx = _play(bus, state)
        assert ctx.extra["21_or_bust"]["total"] == 20
        assert inv.resources == 11

    def test_bust_gains_nothing(self, setup):
        """-8 tokens count as 8: 8,16,24 → bust, no resources."""
        state, bus, inv, impl, bag = setup
        bag.tokens = [ChaosTokenType.MINUS_8]
        ctx = _play(bus, state)
        assert ctx.extra["21_or_bust"]["total"] == 24
        assert ctx.extra["21_or_bust"]["gained"] == 0
        assert inv.resources == 5

    def test_elder_sign_eleven_then_ones_to_19(self, setup):
        """Elder sign reads 11 while total ≤10, then 1: 11→12→…→19, gain 5."""
        state, bus, inv, impl, bag = setup
        bag.tokens = [ChaosTokenType.ELDER_SIGN]
        ctx = _play(bus, state)
        assert ctx.extra["21_or_bust"]["total"] == 19
        assert ctx.extra["21_or_bust"]["gained"] == 5
        assert inv.resources == 10

    def test_low_total_gains_4(self, setup):
        """Stop cap with tiny tokens: total ≤18 → gain 4."""
        state, bus, inv, impl, bag = setup
        bag.tokens = [ChaosTokenType.PLUS_1]
        ctx = _play(bus, state)
        # 15 个 +1（兜底上限）→ 合计15 → 4资源
        assert ctx.extra["21_or_bust"]["total"] == 15
        assert ctx.extra["21_or_bust"]["gained"] == 4
        assert inv.resources == 9
