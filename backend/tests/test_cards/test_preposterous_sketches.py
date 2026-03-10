"""Tests for Preposterous Sketches (Level 0)."""

import pytest
from backend.cards.seeker.preposterous_sketches_lv0 import PreposterousSketches
from backend.engine.event_bus import EventBus, EventContext
from backend.engine.game import Game
from backend.models.enums import Action, CardType, GameEvent, ChaosTokenType, Skill, PlayerClass
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


class TestPreposterousSketches:
    def test_draws_three_on_play(self, setup):
        """Preposterous Sketches draws 3 cards when played."""
        state, bus, inv, loc = setup

        impl = PreposterousSketches("impl_1")
        impl.register(bus, "impl_1")

        initial_hand = len(inv.hand)
        initial_deck = len(inv.deck)

        ctx = EventContext(
            game_state=state,
            event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "preposterous_sketches_lv0"},
        )
        bus.emit(ctx)

        assert len(inv.hand) == initial_hand + 3
        assert len(inv.deck) == initial_deck - 3
        assert inv.hand[-3:] == ["c1", "c2", "c3"]

    def test_partial_draw(self, setup):
        """Only draws available cards when deck has fewer than 3."""
        state, bus, inv, loc = setup
        inv.deck = DrawList(["only_one"])

        impl = PreposterousSketches("impl_1")
        impl.register(bus, "impl_1")

        initial_hand = len(inv.hand)

        ctx = EventContext(
            game_state=state,
            event=GameEvent.CARD_PLAYED,
            investigator_id="inv1",
            extra={"card_id": "preposterous_sketches_lv0"},
        )
        bus.emit(ctx)

        assert len(inv.hand) == initial_hand + 1
        assert len(inv.deck) == 0
        assert inv.hand[-1] == "only_one"

    def test_action_play_triggers_effect(self):
        """Playing the event via ActionResolver should trigger its implementation."""
        g = Game("test")

        inv_data = make_investigator_data()
        g.register_card_data(inv_data)
        loc_data = make_location_data(clue_value=3, connections=[])
        g.register_card_data(loc_data)

        # Card data
        card_data = __import__("backend.models.state", fromlist=["CardData"]).CardData(
            id="preposterous_sketches_lv0",
            name="Preposterous Sketches",
            name_cn="荒唐的素描",
            type=CardType.EVENT,
            card_class=PlayerClass.SEEKER,
            cost=2,
        )
        g.register_card_data(card_data)

        g.add_investigator("inv1", inv_data, starting_location="test_location")
        g.add_location("test_location", loc_data, clues=3)
        inv = g.state.get_investigator("inv1")
        inv.resources = 5
        inv.actions_remaining = 3
        inv.hand = ["preposterous_sketches_lv0"]
        inv.deck = ["c1", "c2", "c3", "c4"]

        g.card_registry.register_class(PreposterousSketches)

        ok = g.action_resolver.perform_action("inv1", Action.PLAY, card_id="preposterous_sketches_lv0")
        assert ok
        # Played 1 (removed from hand), drew 3 -> hand has 3 drawn cards
        assert len(inv.hand) == 3
        assert inv.discard == ["preposterous_sketches_lv0"]
        assert inv.hand == ["c1", "c2", "c3"]
