"""Tests for Magnifying Glass (Level 0)."""

import pytest
from backend.cards.seeker.magnifying_glass_lv0 import MagnifyingGlass
from backend.engine.game import Game
from backend.models.enums import Action, CardType, ChaosTokenType, PlayerClass, SlotType
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(intellect=3)
    g.register_card_data(inv_data)

    loc = make_location_data(shroud=3, clue_value=3)
    g.register_card_data(loc)

    mag_data = CardData(
        id="magnifying_glass_lv0", name="Magnifying Glass", name_cn="放大镜",
        type=CardType.ASSET, card_class=PlayerClass.SEEKER, cost=1,
        slots=[SlotType.HAND], skill_icons={"intellect": 1},
    )
    g.register_card_data(mag_data)

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=3)

    g.card_registry.register_class(MagnifyingGlass)
    return g


def _equip_mag_glass(game):
    inv = game.state.get_investigator("inv1")
    instance_id = game.state.next_instance_id()
    card_inst = CardInstance(
        instance_id=instance_id, card_id="magnifying_glass_lv0",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND],
    )
    game.state.cards_in_play[instance_id] = card_inst
    inv.play_area.append(instance_id)
    game.card_registry.activate_card("magnifying_glass_lv0", instance_id, game.event_bus)
    return instance_id


class TestMagnifyingGlass:
    def test_card_registered(self, game):
        assert "magnifying_glass_lv0" in game.card_registry.registered_cards

    def test_intellect_bonus_helps_investigate(self, game):
        """Magnifying Glass +1 intellect helps pass investigate test."""
        _equip_mag_glass(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        # Intellect 3 + 1 mag glass = 4 >= shroud 3 -> success
        game.action_resolver.perform_action("inv1", Action.INVESTIGATE)
        assert inv.clues == 1

    def test_without_mag_glass_harder(self, game):
        """Without Magnifying Glass, same test with -1 token fails."""
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_1]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        # Intellect 3 + (-1) = 2 < shroud 3 -> fail
        game.action_resolver.perform_action("inv1", Action.INVESTIGATE)
        assert inv.clues == 0
