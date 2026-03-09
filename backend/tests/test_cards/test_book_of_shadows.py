"""Tests for Book of Shadows (Level 3)."""

import pytest
from backend.cards.mystic.book_of_shadows_lv3 import BookOfShadows
from backend.engine.event_bus import EventBus
from backend.models.state import GameState, ScenarioState
from backend.tests.conftest import make_asset_data


@pytest.fixture
def setup():
    state = GameState(scenario=ScenarioState(scenario_id="test"))
    bus = EventBus()

    card_data = make_asset_data(
        id="book_of_shadows_lv3", name="Book of Shadows",
        traits=["item", "tome"],
    )
    state.card_database["book_of_shadows_lv3"] = card_data

    impl = BookOfShadows("inst_bos")
    impl.register(bus, "inst_bos")

    return state, bus, impl


class TestBookOfShadows:
    def test_card_id(self, setup):
        state, bus, impl = setup
        assert impl.card_id == "book_of_shadows_lv3"

    def test_card_data(self, setup):
        state, bus, impl = setup
        card_data = state.card_database["book_of_shadows_lv3"]
        assert card_data.name == "Book of Shadows"
