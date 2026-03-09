"""Tests for Old Book of Lore (Level 0)."""

import pytest
from backend.cards.seeker.old_book_of_lore_lv0 import OldBookOfLore
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import GameState, InvestigatorState, LocationState, ScenarioState, CardInstance
from backend.tests.conftest import make_investigator_data, make_location_data, make_asset_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data(intellect=3)
    state.card_database[inv_data.id] = inv_data

    book_data = make_asset_data(
        id="old_book_of_lore_lv0", name="Old Book of Lore",
        traits=["tome"], skill_icons={"willpower": 1},
    )
    state.card_database["old_book_of_lore_lv0"] = book_data

    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="test_location",
        deck=["card_a", "card_b", "card_c"],
    )
    state.investigators["inv1"] = inv

    loc = LocationState(location_id="test_location", card_data=loc_data, clues=2)
    state.locations["test_location"] = loc

    impl = OldBookOfLore("inst_book")
    impl.register(bus, "inst_book")

    ci = CardInstance(instance_id="inst_book", card_id="old_book_of_lore_lv0", owner_id="inv1", controller_id="inv1")
    state.cards_in_play["inst_book"] = ci
    inv.play_area.append("inst_book")

    return state, bus, inv, impl


class TestOldBookOfLore:
    def test_activate_draws_card(self, setup):
        """Activating Old Book of Lore draws the top card from the deck."""
        state, bus, inv, impl = setup
        assert len(inv.deck) == 3
        assert len(inv.hand) == 0

        ctx = EventContext(
            game_state=state,
            event=GameEvent.CARD_EXHAUSTED,
            investigator_id="inv1",
        )
        impl.activate(ctx)

        assert len(inv.hand) == 1
        assert inv.hand[0] == "card_a"
        assert len(inv.deck) == 2

    def test_provides_willpower_icon(self, setup):
        """Old Book of Lore card data has willpower skill icon."""
        state, bus, inv, impl = setup
        card_data = state.card_database["old_book_of_lore_lv0"]
        assert card_data.skill_icons.get("willpower") == 1
