"""Tests for Wendy's Amulet — Wendy Adams signature asset."""

import pytest
from backend.cards.neutral.wendys_amulet import WendysAmulet
from backend.engine.game import Game
from backend.models.enums import Action, CardType, PlayerClass, SlotType
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import make_event_data, make_investigator_data, make_location_data


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)

    loc = make_location_data()
    g.register_card_data(loc)

    amulet_data = CardData(
        id="wendys_amulet", name="Wendy's Amulet", name_cn="温蒂的护身符",
        type=CardType.ASSET, card_class=PlayerClass.NEUTRAL, cost=2,
        slots=[SlotType.ACCESSORY], traits=["item", "relic"], unique=True,
    )
    g.register_card_data(amulet_data)

    event_data = make_event_data(id="test_event", name="Test Event", cost=1)
    g.register_card_data(event_data)

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)

    g.card_registry.register_class(WendysAmulet)
    return g


def _equip_amulet(game):
    inv = game.state.get_investigator("inv1")
    instance_id = game.state.next_instance_id()
    card_inst = CardInstance(
        instance_id=instance_id, card_id="wendys_amulet",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.ACCESSORY],
    )
    game.state.cards_in_play[instance_id] = card_inst
    inv.play_area.append(instance_id)
    game.card_registry.activate_card("wendys_amulet", instance_id, game.event_bus)
    return instance_id


class TestWendysAmulet:
    def test_card_registered(self, game):
        assert "wendys_amulet" in game.card_registry.registered_cards

    def test_played_event_goes_to_deck_bottom(self, game):
        """Forced: after you play an event, place it on the bottom of your
        deck instead of the discard pile."""
        _equip_amulet(game)
        inv = game.state.get_investigator("inv1")
        inv.hand = ["test_event"]
        inv.deck = ["c1", "c2"]
        inv.resources = 5
        inv.actions_remaining = 3

        ok = game.action_resolver.perform_action(
            "inv1", Action.PLAY, card_id="test_event",
        )
        assert ok
        assert "test_event" not in inv.discard
        assert inv.deck == ["c1", "c2", "test_event"]
        assert inv.resources == 4  # cost paid

    def test_play_top_event_from_discard(self, game):
        """May play the topmost event in the discard pile as if it were in hand."""
        amulet_id = _equip_amulet(game)
        inv = game.state.get_investigator("inv1")
        inv.discard = ["test_event"]
        inv.deck = ["c1"]
        inv.resources = 5
        inv.actions_remaining = 3

        impl = game.card_registry.active_instances[amulet_id]
        assert impl.top_event_in_discard(game.state, "inv1") == "test_event"

        ok = impl.play_top_event_from_discard(game, "inv1")
        assert ok
        assert "test_event" not in inv.hand
        # Forced effect also applies: bottom of deck, not discard
        assert "test_event" not in inv.discard
        assert inv.deck == ["c1", "test_event"]
        assert inv.resources == 4

    def test_top_event_ignores_non_events(self, game):
        """Only the topmost *event* is playable from the discard pile."""
        amulet_id = _equip_amulet(game)
        inv = game.state.get_investigator("inv1")
        # Register a non-event card and put it on top of the discard pile
        asset_data = CardData(
            id="test_asset", name="Test Asset", name_cn="测试支援",
            type=CardType.ASSET, card_class=PlayerClass.NEUTRAL, cost=1,
        )
        game.register_card_data(asset_data)
        inv.discard = ["test_event", "test_asset"]

        impl = game.card_registry.active_instances[amulet_id]
        assert impl.top_event_in_discard(game.state, "inv1") == "test_event"

    def test_event_discards_normally_without_amulet(self, game):
        """Without the amulet in play, played events go to the discard pile."""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["test_event"]
        inv.deck = ["c1"]
        inv.resources = 5

        game.action_resolver.perform_action("inv1", Action.PLAY, card_id="test_event")
        assert "test_event" in inv.discard
        assert inv.deck == ["c1"]
