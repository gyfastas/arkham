"""Tests for Leo De Luca (Level 0 and Level 1)."""

import pytest
from backend.cards.rogue.leo_de_luca_lv0 import LeoDeLuca
from backend.cards.rogue.leo_de_luca_lv1 import LeoDeLucaLv1
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import GameState, InvestigatorState, ScenarioState, CardInstance
from backend.tests.conftest import make_investigator_data, make_asset_data


@pytest.fixture
def setup_lv0():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
    )
    inv.actions_remaining = 3
    state.investigators["inv1"] = inv

    impl = LeoDeLuca("leo_inst")
    impl.register(bus, "leo_inst")

    ci = CardInstance(instance_id="leo_inst", card_id="leo_de_luca_lv0", owner_id="inv1", controller_id="inv1")
    state.cards_in_play["leo_inst"] = ci
    inv.play_area.append("leo_inst")

    return state, bus, inv, impl


@pytest.fixture
def setup_lv1():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
    )
    inv.actions_remaining = 3
    state.investigators["inv1"] = inv

    impl = LeoDeLucaLv1("leo1_inst")
    impl.register(bus, "leo1_inst")

    ci = CardInstance(instance_id="leo1_inst", card_id="leo_de_luca_lv1", owner_id="inv1", controller_id="inv1")
    state.cards_in_play["leo1_inst"] = ci
    inv.play_area.append("leo1_inst")

    return state, bus, inv, impl


class TestLeoDeLuca:
    def test_grant_extra_action_lv0(self, setup_lv0):
        """Leo De Luca lv0 grants +1 action at investigation phase start."""
        state, bus, inv, impl = setup_lv0

        ctx = EventContext(
            game_state=state,
            event=GameEvent.INVESTIGATION_PHASE_BEGINS,
            investigator_id="inv1",
            extra={},
        )
        bus.emit(ctx)

        assert inv.actions_remaining == 4

    def test_no_action_when_not_in_play(self, setup_lv0):
        """No extra action if Leo is not in play area."""
        state, bus, inv, impl = setup_lv0
        inv.play_area.clear()

        ctx = EventContext(
            game_state=state,
            event=GameEvent.INVESTIGATION_PHASE_BEGINS,
            investigator_id="inv1",
            extra={},
        )
        bus.emit(ctx)

        assert inv.actions_remaining == 3

    def test_grant_extra_action_lv1(self, setup_lv1):
        """Leo De Luca lv1 also grants +1 action."""
        state, bus, inv, impl = setup_lv1

        ctx = EventContext(
            game_state=state,
            event=GameEvent.INVESTIGATION_PHASE_BEGINS,
            investigator_id="inv1",
            extra={},
        )
        bus.emit(ctx)

        assert inv.actions_remaining == 4
