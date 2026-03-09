"""Tests for Research Librarian (Level 0)."""

import pytest
from backend.cards.seeker.research_librarian_lv0 import ResearchLibrarian
from backend.engine.event_bus import EventBus, EventContext
from backend.models.enums import GameEvent
from backend.models.state import GameState, InvestigatorState, LocationState, ScenarioState, CardInstance
from backend.tests.conftest import make_investigator_data, make_location_data, make_asset_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    inv_data = make_investigator_data()
    state.card_database[inv_data.id] = inv_data

    librarian_data = make_asset_data(
        id="research_librarian_lv0", name="Research Librarian",
        traits=["ally", "miskatonic"],
    )
    state.card_database["research_librarian_lv0"] = librarian_data

    tome_data = make_asset_data(
        id="ancient_tome", name="Ancient Tome",
        traits=["tome"],
    )
    state.card_database["ancient_tome"] = tome_data

    loc_data = make_location_data()
    state.card_database[loc_data.id] = loc_data

    inv = InvestigatorState(
        investigator_id="inv1",
        card_data=inv_data,
        location_id="test_location",
        deck=["card_a", "ancient_tome", "card_b"],
    )
    state.investigators["inv1"] = inv

    loc = LocationState(location_id="test_location", card_data=loc_data, clues=2)
    state.locations["test_location"] = loc

    impl = ResearchLibrarian("inst_librarian")
    impl.register(bus, "inst_librarian")

    ci = CardInstance(instance_id="inst_librarian", card_id="research_librarian_lv0", owner_id="inv1", controller_id="inv1")
    state.cards_in_play["inst_librarian"] = ci
    inv.play_area.append("inst_librarian")

    # Research Librarian implementation calls get_card_definition(),
    # which is an alias for get_card_data() not present on GameState.
    # Patch it here so the test can exercise the card logic.
    state.get_card_definition = state.get_card_data

    return state, bus, inv, impl


class TestResearchLibrarian:
    def test_enters_play_searches_tome(self, setup):
        """When Research Librarian enters play, a Tome card is moved from deck to hand."""
        state, bus, inv, impl = setup
        assert "ancient_tome" in inv.deck
        assert "ancient_tome" not in inv.hand

        ctx = EventContext(
            game_state=state,
            event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1",
            target="inst_librarian",
        )
        bus.emit(ctx)

        assert "ancient_tome" in inv.hand
        assert "ancient_tome" not in inv.deck

    def test_no_tome_in_deck(self, setup):
        """If no Tome in deck, nothing changes."""
        state, bus, inv, impl = setup
        # Remove the tome from the deck
        inv.deck = ["card_a", "card_b", "card_c"]

        ctx = EventContext(
            game_state=state,
            event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id="inv1",
            target="inst_librarian",
        )
        bus.emit(ctx)

        assert len(inv.hand) == 0
        assert inv.deck == ["card_a", "card_b", "card_c"]
