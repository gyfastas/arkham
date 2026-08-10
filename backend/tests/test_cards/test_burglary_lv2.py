"""Tests for Burglary (Level 2)."""

import pytest
from backend.cards.rogue.burglary_lv2 import BurglaryLv2
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, Skill
from backend.models.state import (
    CardInstance, GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data(intellect=4)
    state.card_database[inv_data.id] = inv_data
    loc_data = make_location_data(id="loc1")
    state.card_database["loc1"] = loc_data
    state.locations["loc1"] = LocationState(
        location_id="loc1", card_data=loc_data, clues=2, revealed=True,
    )
    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="loc1",
    )
    inv.resources = 5
    state.investigators["inv1"] = inv

    impl = BurglaryLv2("burglary_inst")
    impl.register(bus, "burglary_inst")
    ci = CardInstance(
        instance_id="burglary_inst", card_id="burglary_lv2",
        owner_id="inv1", controller_id="inv1",
    )
    state.cards_in_play["burglary_inst"] = ci
    inv.play_area.append("burglary_inst")
    return state, bus, inv, impl, ci


def _succeed_and_discover(bus, state, modified, difficulty):
    """模拟：武装后调查成功（margin）并由引擎发现1个线索。"""
    bus.emit(EventContext(
        game_state=state, event=GameEvent.SKILL_TEST_SUCCESSFUL,
        investigator_id="inv1", skill_type=Skill.INTELLECT,
        success=True, modified_skill=modified, difficulty=difficulty,
    ))
    loc = state.locations["loc1"]
    inv = state.investigators["inv1"]
    loc.clues -= 1
    inv.clues += 1
    ctx = EventContext(
        game_state=state, event=GameEvent.CLUE_DISCOVERED,
        investigator_id="inv1", location_id="loc1", amount=1,
    )
    bus.emit(ctx)
    return ctx


class TestBurglaryLv2:
    def test_base_2_resources(self, setup):
        """成功（超0点）：不发现线索，获得2资源。"""
        state, bus, inv, impl, ci = setup
        assert impl.activate(state, "inv1") is True
        assert ci.exhausted is True
        ctx = _succeed_and_discover(bus, state, modified=4, difficulty=4)
        assert inv.resources == 7
        assert inv.clues == 0
        assert state.locations["loc1"].clues == 2
        assert ctx.extra["burglary_lv2_resources"] == 2

    def test_margin_adds_resources_capped_3(self, setup):
        """每超1点+1资源，至多+3（超5点 → 2+3=5资源）。"""
        state, bus, inv, impl, ci = setup
        impl.activate(state, "inv1")
        ctx = _succeed_and_discover(bus, state, modified=9, difficulty=4)
        assert ctx.extra["burglary_lv2_resources"] == 5
        assert inv.resources == 10

    def test_margin_2_gives_4(self, setup):
        state, bus, inv, impl, ci = setup
        impl.activate(state, "inv1")
        ctx = _succeed_and_discover(bus, state, modified=6, difficulty=4)
        assert ctx.extra["burglary_lv2_resources"] == 4
        assert inv.resources == 9

    def test_no_effect_when_not_armed(self, setup):
        state, bus, inv, impl, ci = setup
        ctx = EventContext(
            game_state=state, event=GameEvent.CLUE_DISCOVERED,
            investigator_id="inv1", location_id="loc1", amount=1,
        )
        bus.emit(ctx)
        assert inv.resources == 5
