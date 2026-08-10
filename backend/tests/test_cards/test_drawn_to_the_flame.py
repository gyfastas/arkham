"""Tests for Drawn to the Flame (Level 0). (01064)

先抽遭遇牌堆顶1张（ENCOUNTER_CARD_DRAWN 流程），然后在所在地点发现2条线索。
"""

import pytest
from backend.cards.mystic.drawn_to_the_flame_lv0 import DrawnToTheFlame
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import make_event_data, make_investigator_data, make_location_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data

    card_data = make_event_data(
        id="drawn_to_the_flame_lv0", name="Drawn to the Flame",
    )
    state.card_database["drawn_to_the_flame_lv0"] = card_data
    state.card_database["frozen_in_fear"] = make_event_data(
        id="frozen_in_fear", name="Frozen in Fear",
    )

    loc_data = make_location_data(shroud=2)
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="test_location",
        deck=["card_a", "card_b"],
    )
    state.investigators["inv1"] = inv

    loc = LocationState(location_id="test_location", card_data=loc_data, clues=3)
    state.locations["test_location"] = loc

    impl = DrawnToTheFlame("inst_dttf")
    impl.register(bus, "inst_dttf")

    return state, bus, inv, loc


def _play(state, bus):
    ctx = EventContext(
        event=GameEvent.CARD_PLAYED,
        game_state=state,
        investigator_id="inv1",
        extra={"card_id": "drawn_to_the_flame_lv0"},
    )
    bus.emit(ctx)
    return ctx


class TestDrawnToTheFlame:
    def test_discover_2_clues(self, setup):
        """Playing Drawn to the Flame discovers 2 clues at your location."""
        state, bus, inv, loc = setup
        initial_clues = inv.clues
        initial_loc_clues = loc.clues

        _play(state, bus)

        assert inv.clues == initial_clues + 2
        assert loc.clues == initial_loc_clues - 2

    def test_draws_top_encounter_card_first(self, setup):
        """先抽遭遇牌堆顶牌（入遭遇弃牌堆），再发现线索。"""
        state, bus, inv, loc = setup
        state.scenario.encounter_deck = ["frozen_in_fear", "other_enc"]

        drawn_events = []
        from backend.models.enums import GameEvent as GE

        def spy(ctx):
            drawn_events.append(ctx.extra.get("card_id"))

        bus.register(GE.ENCOUNTER_CARD_DRAWN, spy)

        ctx = _play(state, bus)

        assert drawn_events == ["frozen_in_fear"]
        assert ctx.extra["drawn_to_the_flame_encounter"] == "frozen_in_fear"
        assert state.scenario.encounter_deck == ["other_enc"]
        assert state.scenario.encounter_discard == ["frozen_in_fear"]
        assert inv.clues == 2

    def test_empty_encounter_deck_still_discovers(self, setup):
        """遭遇牌堆为空时跳过抽牌，仍发现2线索。"""
        state, bus, inv, loc = setup
        state.scenario.encounter_deck = []
        ctx = _play(state, bus)
        assert "drawn_to_the_flame_encounter" not in ctx.extra
        assert inv.clues == 2
        assert loc.clues == 1
