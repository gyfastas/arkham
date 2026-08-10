"""Tests for Unscrupulous Loan (Level 3)."""

import pytest

from backend.cards.rogue.unscrupulous_loan_lv3 import UnscrupulousLoan
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1")
    inv.resources = 3
    state.investigators["inv1"] = inv
    inst = CardInstance(
        instance_id="loan_inst", card_id="unscrupulous_loan_lv3",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["loan_inst"] = inst
    inv.play_area.append("loan_inst")
    impl = UnscrupulousLoan("loan_inst")
    impl.register(bus, "loan_inst")
    return state, bus, inv, inst


class TestUnscrupulousLoan:
    def test_gain_ten_on_enter(self, setup):
        state, bus, inv, inst = setup
        ctx = EventContext(
            game_state=state,
            event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1",
            target="loan_inst",
            extra={"card_id": "unscrupulous_loan_lv3"},
        )
        bus.emit(ctx)
        assert inv.resources == 13
        assert ctx.extra["unscrupulous_loan_gained"] == 10

    def test_exiled_when_defeated_below_ten(self, setup):
        state, bus, inv, inst = setup
        inv.resources = 4
        ctx = EventContext(
            game_state=state,
            event=GameEvent.INVESTIGATOR_DEFEATED,
            investigator_id="inv1",
        )
        bus.emit(ctx)
        assert ctx.extra["unscrupulous_loan_exiled"] is True
        assert "loan_inst" not in inv.play_area
        assert "loan_inst" not in state.cards_in_play
        assert "unscrupulous_loan_lv3" in state.scenario.vars["removed_from_game"]

    def test_not_exiled_with_ten_resources(self, setup):
        state, bus, inv, inst = setup
        inv.resources = 12
        ctx = EventContext(
            game_state=state,
            event=GameEvent.INVESTIGATOR_DEFEATED,
            investigator_id="inv1",
        )
        bus.emit(ctx)
        assert "unscrupulous_loan_exiled" not in ctx.extra
        assert "loan_inst" in inv.play_area

    def test_other_investigator_defeat_ignored(self, setup):
        state, bus, inv, inst = setup
        inv2_data = make_investigator_data(id="inv2_data")
        state.card_database["inv2_data"] = inv2_data
        inv2 = InvestigatorState(
            investigator_id="inv2", card_data=inv2_data, location_id="loc1")
        inv2.resources = 0
        state.investigators["inv2"] = inv2
        ctx = EventContext(
            game_state=state,
            event=GameEvent.INVESTIGATOR_DEFEATED,
            investigator_id="inv2",
        )
        bus.emit(ctx)
        assert "unscrupulous_loan_exiled" not in ctx.extra
        assert "loan_inst" in inv.play_area
