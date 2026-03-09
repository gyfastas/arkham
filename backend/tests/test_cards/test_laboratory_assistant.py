"""Tests for Laboratory Assistant (Level 0)."""

import pytest
from backend.cards.seeker.laboratory_assistant_lv0 import LaboratoryAssistant
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent, ChaosTokenType, Skill
from backend.models.state import GameState, InvestigatorState, LocationState, ScenarioState, CardInstance
from backend.tests.conftest import make_investigator_data, make_location_data


class DrawList(list):
    """List subclass with a draw() method that pops from index 0."""

    def draw(self):
        return self.pop(0) if self else None


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()
    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data
    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data
    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="test_location",
        deck=DrawList(["c1", "c2", "c3", "c4", "c5"]),
    )
    state.investigators["inv1"] = inv
    loc = LocationState(location_id="test_location", card_data=loc_data, clues=3)
    state.locations["test_location"] = loc
    return state, bus, inv, loc


class TestLaboratoryAssistant:
    def test_draws_two_on_enter(self, setup):
        """Laboratory Assistant draws 2 cards when entering play."""
        state, bus, inv, loc = setup
        inst_id = "inst_1"
        ci = CardInstance(
            instance_id=inst_id,
            card_id="laboratory_assistant_lv0",
            owner_id="inv1",
            controller_id="inv1",
        )
        state.cards_in_play[inst_id] = ci
        inv.play_area.append(inst_id)

        impl = LaboratoryAssistant(inst_id)
        impl.register(bus, inst_id)

        initial_hand = len(inv.hand)
        initial_deck = len(inv.deck)

        ctx = EventContext(
            game_state=state,
            event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1",
            target=inst_id,
        )
        bus.emit(ctx)

        assert len(inv.hand) == initial_hand + 2
        assert len(inv.deck) == initial_deck - 2
        assert inv.hand[-2:] == ["c1", "c2"]

    def test_no_draw_wrong_target(self, setup):
        """No cards drawn when a different card enters play."""
        state, bus, inv, loc = setup
        inst_id = "inst_1"
        ci = CardInstance(
            instance_id=inst_id,
            card_id="laboratory_assistant_lv0",
            owner_id="inv1",
            controller_id="inv1",
        )
        state.cards_in_play[inst_id] = ci
        inv.play_area.append(inst_id)

        impl = LaboratoryAssistant(inst_id)
        impl.register(bus, inst_id)

        initial_hand = len(inv.hand)
        initial_deck = len(inv.deck)

        ctx = EventContext(
            game_state=state,
            event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1",
            target="some_other_card",
        )
        bus.emit(ctx)

        assert len(inv.hand) == initial_hand
        assert len(inv.deck) == initial_deck
