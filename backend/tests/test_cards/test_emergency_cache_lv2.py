"""Tests for Emergency Cache (Level 2)."""

import pytest
from backend.cards.neutral.emergency_cache_lv2 import EmergencyCacheLv2
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
        id="emergency_cache_lv2", name="Emergency Cache", name_cn="应急物品",
        type=CardType.EVENT, card_class=PlayerClass.NEUTRAL, cost=0,
        traits=["supply"],
    )
    g.register_card_data(cache_data)

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)

    g.card_registry.register_class(EmergencyCacheLv2)
    impl = EmergencyCacheLv2("event_listener")
    impl.register(g.event_bus, "event_listener")

    return g


class TestEmergencyCacheLv2:
    def test_card_registered(self, game):
        assert "emergency_cache_lv2" in game.card_registry.registered_cards

    def test_gain_3_resources_and_draw(self, game):
        inv = game.state.get_investigator("inv1")
        inv.hand.append("emergency_cache_lv2")
        inv.resources = 2
        inv.actions_remaining = 3
        inv.deck = ["card_a", "card_b"]

        game.action_resolver.perform_action("inv1", Action.PLAY, card_id="emergency_cache_lv2")
        # Cost 0, gain 3 resources -> 2 + 3 = 5
        assert inv.resources == 5
        # Drew 1 card from deck
        assert "card_a" in inv.hand
