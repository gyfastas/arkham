"""Tests for Priest of Two Faiths (Level 1)."""

import pytest

from backend.cards.rogue.priest_of_two_faiths_lv1 import PriestOfTwoFaiths
from backend.engine.event_bus import EventBus, EventContext
from backend.models.chaos import ChaosBag
from backend.models.enums import ChaosTokenType, GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    bag = ChaosBag()
    bag.seed(1)
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    state.investigators["inv1"] = inv
    inst = CardInstance(
        instance_id="priest_inst", card_id="priest_of_two_faiths_lv1",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["priest_inst"] = inst
    inv.play_area.append("priest_inst")
    impl = PriestOfTwoFaiths("priest_inst")
    impl.register(bus, "priest_inst")
    impl.bind_chaos_bag(bag)
    return state, bus, bag, inv, inst


class TestPriestOfTwoFaiths:
    def test_enters_play_adds_three_bless(self, setup):
        state, bus, bag, inv, inst = setup
        before = bag.tokens.count(ChaosTokenType.BLESS)
        ctx = EventContext(
            game_state=state,
            event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1",
            target="priest_inst",
            extra={"card_id": "priest_of_two_faiths_lv1"},
        )
        bus.emit(ctx)
        assert bag.tokens.count(ChaosTokenType.BLESS) == before + 3
        assert ctx.extra["priest_bless_added"] == 3

    def test_upkeep_end_adds_curse(self, setup):
        state, bus, bag, inv, inst = setup
        before = bag.tokens.count(ChaosTokenType.CURSE)
        bus.emit(EventContext(
            game_state=state,
            event=GameEvent.UPKEEP_PHASE_ENDS,
        ))
        assert bag.tokens.count(ChaosTokenType.CURSE) == before + 1
        # 神父仍在场（自动选择加诅咒而非丢弃）
        assert "priest_inst" in inv.play_area

    def test_no_curse_when_not_in_play(self, setup):
        state, bus, bag, inv, inst = setup
        inv.play_area.remove("priest_inst")
        before = bag.tokens.count(ChaosTokenType.CURSE)
        bus.emit(EventContext(
            game_state=state,
            event=GameEvent.UPKEEP_PHASE_ENDS,
        ))
        assert bag.tokens.count(ChaosTokenType.CURSE) == before
