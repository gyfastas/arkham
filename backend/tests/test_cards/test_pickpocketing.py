"""Tests for Pickpocketing (Level 0)."""

import pytest
from backend.cards.rogue.pickpocketing_lv0 import Pickpocketing
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import GameState, InvestigatorState, ScenarioState, CardInstance
from backend.tests.conftest import make_investigator_data, make_asset_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="loc1",
        deck=["card_a", "card_b", "card_c"],
    )
    state.investigators["inv1"] = inv

    impl = Pickpocketing("pickpocket_inst")
    impl.register(bus, "pickpocket_inst")

    ci = CardInstance(instance_id="pickpocket_inst", card_id="pickpocketing_lv0", owner_id="inv1", controller_id="inv1")
    state.cards_in_play["pickpocket_inst"] = ci
    inv.play_area.append("pickpocket_inst")

    return state, bus, inv, impl


class TestPickpocketing:
    def test_draw_card_on_evade(self, setup):
        """After evading an enemy, draw 1 card."""
        state, bus, inv, impl = setup
        initial_hand = len(inv.hand)
        initial_deck = len(inv.deck)

        ctx = EventContext(
            game_state=state,
            event=GameEvent.ENEMY_EVADED,
            investigator_id="inv1",
            extra={},
        )
        bus.emit(ctx)

        assert len(inv.hand) == initial_hand + 1
        assert len(inv.deck) == initial_deck - 1

    def test_no_draw_when_not_in_play(self, setup):
        """No card drawn if Pickpocketing is not in play area."""
        state, bus, inv, impl = setup
        inv.play_area.clear()
        initial_hand = len(inv.hand)

        ctx = EventContext(
            game_state=state,
            event=GameEvent.ENEMY_EVADED,
            investigator_id="inv1",
            extra={},
        )
        bus.emit(ctx)

        assert len(inv.hand) == initial_hand
