"""Tests for Heirloom of Hyperborea — Agnes Baker signature asset."""

import pytest
from backend.cards.neutral.heirloom_of_hyperborea import HeirloomOfHyperborea
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

    heirloom_data = CardData(
        id="heirloom_of_hyperborea", name="Heirloom of Hyperborea",
        name_cn="许珀耳玻瑞亚传家宝",
        type=CardType.ASSET, card_class=PlayerClass.NEUTRAL, cost=3,
        slots=[SlotType.ACCESSORY], traits=["item", "relic"], unique=True,
    )
    g.register_card_data(heirloom_data)

    spell_event = make_event_data(id="test_spell", name="Test Spell", cost=1)
    spell_event.traits = ["spell"]
    g.register_card_data(spell_event)

    plain_event = make_event_data(id="test_event", name="Test Event", cost=1)
    plain_event.traits = ["tactic"]
    g.register_card_data(plain_event)

    spell_asset = CardData(
        id="test_spell_asset", name="Test Spell Asset", name_cn="测试法术支援",
        type=CardType.ASSET, card_class=PlayerClass.NEUTRAL, cost=1,
        traits=["spell"], slots=[SlotType.ARCANE],
    )
    g.register_card_data(spell_asset)

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)

    g.card_registry.register_class(HeirloomOfHyperborea)
    return g


def _equip_heirloom(game):
    inv = game.state.get_investigator("inv1")
    instance_id = game.state.next_instance_id()
    card_inst = CardInstance(
        instance_id=instance_id, card_id="heirloom_of_hyperborea",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.ACCESSORY],
    )
    game.state.cards_in_play[instance_id] = card_inst
    inv.play_area.append(instance_id)
    game.card_registry.activate_card("heirloom_of_hyperborea", instance_id, game.event_bus)
    return instance_id


def _prep_inv(game, hand, deck):
    inv = game.state.get_investigator("inv1")
    inv.hand = list(hand)
    inv.deck = list(deck)
    inv.resources = 10
    inv.actions_remaining = 3
    return inv


class TestHeirloomOfHyperborea:
    def test_card_registered(self, game):
        assert "heirloom_of_hyperborea" in game.card_registry.registered_cards

    def test_draw_after_playing_spell_event(self, game):
        """After you play a Spell event, draw 1 card."""
        _equip_heirloom(game)
        inv = _prep_inv(game, hand=["test_spell"], deck=["c1", "c2"])

        game.action_resolver.perform_action("inv1", Action.PLAY, card_id="test_spell")
        assert "c1" in inv.hand
        assert inv.deck == ["c2"]

    def test_no_draw_on_non_spell(self, game):
        """Playing a non-Spell card does not trigger the draw."""
        _equip_heirloom(game)
        inv = _prep_inv(game, hand=["test_event"], deck=["c1"])

        game.action_resolver.perform_action("inv1", Action.PLAY, card_id="test_event")
        assert "c1" not in inv.hand
        assert inv.deck == ["c1"]

    def test_draw_after_playing_spell_asset(self, game):
        """Playing a Spell asset (enters play) also triggers the draw."""
        _equip_heirloom(game)
        inv = _prep_inv(game, hand=["test_spell_asset"], deck=["c1"])

        game.action_resolver.perform_action("inv1", Action.PLAY, card_id="test_spell_asset")
        assert "c1" in inv.hand
        assert inv.deck == []
