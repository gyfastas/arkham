"""Tests for Another Day, Another Dollar (Level 3)."""

import pytest
from backend.cards.rogue.another_day_another_dollar_lv3 import (
    AnotherDayAnotherDollar,
)
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
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    inv.resources = 5
    state.investigators["inv1"] = inv

    impl = AnotherDayAnotherDollar("adad_inst")
    impl.register(bus, "adad_inst")
    ci = CardInstance(
        instance_id="adad_inst", card_id="another_day_another_dollar_lv3",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["adad_inst"] = ci
    inv.play_area.append("adad_inst")
    return state, bus, inv, impl, ci


class TestAnotherDayAnotherDollar:
    def test_plus_2_resources_on_enter(self, setup):
        """永久：入场（开局）时额外获得2资源。"""
        state, bus, inv, impl, ci = setup
        bus.emit(EventContext(
            game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target="adad_inst",
            extra={"card_id": "another_day_another_dollar_lv3"},
        ))
        assert inv.resources == 7

    def test_granted_only_once(self, setup):
        state, bus, inv, impl, ci = setup
        ctx = EventContext(
            game_state=state, event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1", target="adad_inst",
            extra={"card_id": "another_day_another_dollar_lv3"},
        )
        bus.emit(ctx)
        bus.emit(ctx)
        assert inv.resources == 7

    def test_public_game_start_entry(self, setup):
        """公开方法入口同样只生效一次。"""
        state, bus, inv, impl, ci = setup
        assert impl.apply_game_start(state, "inv1") is True
        assert inv.resources == 7
        assert impl.apply_game_start(state, "inv1") is False
