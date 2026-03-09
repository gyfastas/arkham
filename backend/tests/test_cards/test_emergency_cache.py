"""Tests for Emergency Cache (Level 0)."""

import pytest
from backend.cards.neutral.emergency_cache_lv0 import EmergencyCache
from backend.engine.game import Game
from backend.models.enums import Action, CardType, PlayerClass
from backend.models.state import CardData
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def game():
    g = Game("test")

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)

    loc = make_location_data()
    g.register_card_data(loc)

    cache_data = CardData(
        id="emergency_cache_lv0", name="Emergency Cache", name_cn="应急储备",
        type=CardType.EVENT, card_class=PlayerClass.NEUTRAL, cost=0,
        traits=["supply"],
    )
    g.register_card_data(cache_data)

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)

    # Register the card implementation
    g.card_registry.register_class(EmergencyCache)
    # For events, we register a temporary instance to listen
    impl = EmergencyCache("event_listener")
    impl.register(g.event_bus, "event_listener")

    return g


class TestEmergencyCache:
    def test_card_registered(self, game):
        assert "emergency_cache_lv0" in game.card_registry.registered_cards

    def test_gain_3_resources(self, game):
        inv = game.state.get_investigator("inv1")
        inv.hand.append("emergency_cache_lv0")
        inv.resources = 2
        inv.actions_remaining = 3

        game.action_resolver.perform_action("inv1", Action.PLAY, card_id="emergency_cache_lv0")
        # Cost 0, gain 3 resources -> 2 + 3 = 5
        assert inv.resources == 5

    def test_goes_to_discard(self, game):
        inv = game.state.get_investigator("inv1")
        inv.hand.append("emergency_cache_lv0")
        inv.resources = 5
        inv.actions_remaining = 3

        game.action_resolver.perform_action("inv1", Action.PLAY, card_id="emergency_cache_lv0")
        assert "emergency_cache_lv0" not in inv.hand
        assert "emergency_cache_lv0" in inv.discard
