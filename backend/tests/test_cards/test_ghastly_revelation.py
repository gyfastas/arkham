"""Tests for Ghastly Revelation (Level 0)."""

import pytest
from backend.cards.seeker.ghastly_revelation_lv0 import GhastlyRevelation
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import (
    GameState, InvestigatorState, LocationState, ScenarioState,
)
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(sanity=5)
    state.card_database[inv_data.id] = inv_data
    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1", card_data=inv_data, location_id="test_location",
    )
    state.investigators["inv1"] = inv
    loc = LocationState(location_id="test_location", card_data=loc_data, clues=3)
    state.locations["test_location"] = loc

    impl = GhastlyRevelation("gr_1")
    impl.register(bus, "gr_1")
    return state, bus, inv, loc, impl


def _play(state, bus, **extra):
    ctx = EventContext(
        game_state=state,
        event=GameEvent.CARD_PLAYED,
        investigator_id="inv1",
        extra={"card_id": "ghastly_revelation_lv0", **extra},
    )
    bus.emit(ctx)
    return ctx


class TestGhastlyRevelation:
    def test_discover_three_then_defeated_with_mental_trauma(self, setup):
        """发现3个线索；随后被击败并承受1点精神创伤。"""
        state, bus, inv, loc, impl = setup
        ctx = _play(state, bus)
        assert ctx.extra["ghastly_revelation_clues"] == 3
        assert inv.clues == 3
        assert loc.clues == 0

        assert ctx.extra["ghastly_revelation_defeated"] is True
        assert inv.is_defeated is True  # 恐惧被设为神智上限
        assert inv.horror == inv.sanity
        assert getattr(inv, "mental_trauma", 0) == 1

    def test_defeat_event_emitted(self, setup):
        """被击败时发出 INVESTIGATOR_DEFEATED。"""
        state, bus, inv, loc, impl = setup
        seen = []
        bus.register(
            event=GameEvent.INVESTIGATOR_DEFEATED,
            handler=lambda ctx: seen.append(ctx.investigator_id),
        )
        _play(state, bus)
        assert seen == ["inv1"]

    def test_optional_clue_gift_before_defeat(self, setup):
        """显式参数：击败前可将线索交给其他调查员。"""
        state, bus, inv, loc, impl = setup
        other_data = make_investigator_data(id="inv2", name="Other")
        state.card_database["inv2"] = other_data
        other = InvestigatorState(
            investigator_id="inv2", card_data=other_data,
            location_id="test_location",
        )
        state.investigators["inv2"] = other

        _play(state, bus, give_clues_to="inv2", clue_count=2)
        assert inv.clues == 1
        assert other.clues == 2

    def test_fewer_clues_available(self, setup):
        """地点只有2个线索时只发现2个。"""
        state, bus, inv, loc, impl = setup
        loc.clues = 2
        ctx = _play(state, bus)
        assert ctx.extra["ghastly_revelation_clues"] == 2
        assert inv.clues == 2
