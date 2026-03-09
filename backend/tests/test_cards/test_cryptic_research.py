"""Tests for Cryptic Research (Level 4)."""

import pytest
from backend.cards.seeker.cryptic_research_lv4 import CrypticResearch
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import GameState, InvestigatorState, ScenarioState
from backend.tests.conftest import make_investigator_data, make_event_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data

    cr_data = make_event_data(
        id="cryptic_research_lv4", name="Cryptic Research",
        fast=True,
    )
    state.card_database["cryptic_research_lv4"] = cr_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="test_location",
        deck=["card_a", "card_b", "card_c", "card_d", "card_e"],
    )
    state.investigators["inv1"] = inv

    impl = CrypticResearch("inst_cr")
    impl.register(bus, "inst_cr")

    return state, bus, inv


class TestCrypticResearch:
    def test_draws_three_cards(self, setup):
        """Playing Cryptic Research draws 3 cards."""
        state, bus, inv = setup
        assert len(inv.hand) == 0
        assert len(inv.deck) == 5

        ctx = EventContext(
            game_state=state,
            event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "cryptic_research_lv4"},
        )
        bus.emit(ctx)

        assert len(inv.hand) == 3
        assert inv.hand == ["card_a", "card_b", "card_c"]
        assert len(inv.deck) == 2

    def test_partial_draw(self, setup):
        """If only 2 cards in deck, draws 2 instead of 3."""
        state, bus, inv = setup
        inv.deck = ["card_x", "card_y"]

        ctx = EventContext(
            game_state=state,
            event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "cryptic_research_lv4"},
        )
        bus.emit(ctx)

        assert len(inv.hand) == 2
        assert inv.hand == ["card_x", "card_y"]
        assert len(inv.deck) == 0
