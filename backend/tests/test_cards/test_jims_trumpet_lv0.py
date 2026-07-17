"""Tests for Jim's Trumpet (Level 0) — Jim Culver signature asset."""

import pytest
from backend.cards.neutral.jims_trumpet_lv0 import JimsTrumpet
from backend.engine.game import Game
from backend.models.enums import CardType, ChaosTokenType, PlayerClass, Skill, SlotType
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import make_investigator_data, make_location_data


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(willpower=4)
    g.register_card_data(inv_data)

    loc = make_location_data()
    g.register_card_data(loc)

    trumpet_data = CardData(
        id="jims_trumpet_lv0", name="Jim's Trumpet", name_cn="吉姆的小号",
        type=CardType.ASSET, card_class=PlayerClass.NEUTRAL, cost=2,
        slots=[SlotType.HAND], traits=["item", "instrument", "relic"],
        unique=True,
    )
    g.register_card_data(trumpet_data)

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)

    g.card_registry.register_class(JimsTrumpet)
    return g


def _equip_trumpet(game):
    inv = game.state.get_investigator("inv1")
    instance_id = game.state.next_instance_id()
    card_inst = CardInstance(
        instance_id=instance_id, card_id="jims_trumpet_lv0",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND],
    )
    game.state.cards_in_play[instance_id] = card_inst
    inv.play_area.append(instance_id)
    game.card_registry.activate_card("jims_trumpet_lv0", instance_id, game.event_bus)
    return instance_id


class TestJimsTrumpet:
    def test_card_registered(self, game):
        assert "jims_trumpet_lv0" in game.card_registry.registered_cards

    def test_heal_horror_on_skull(self, game):
        """Skull token revealed: exhaust trumpet to heal 1 horror."""
        trumpet_id = _equip_trumpet(game)
        inv = game.state.get_investigator("inv1")
        inv.horror = 2
        game.chaos_bag.tokens = [ChaosTokenType.SKULL]

        game.skill_test_engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.WILLPOWER,
            difficulty=1,
        )
        assert inv.horror == 1
        assert game.state.get_card_instance(trumpet_id).exhausted

    def test_no_trigger_on_other_token(self, game):
        """Non-skull tokens do not trigger the trumpet."""
        trumpet_id = _equip_trumpet(game)
        inv = game.state.get_investigator("inv1")
        inv.horror = 2
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_1]

        game.skill_test_engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.WILLPOWER,
            difficulty=1,
        )
        assert inv.horror == 2
        assert not game.state.get_card_instance(trumpet_id).exhausted

    def test_no_trigger_when_exhausted(self, game):
        """An exhausted trumpet cannot heal."""
        trumpet_id = _equip_trumpet(game)
        game.state.get_card_instance(trumpet_id).exhausted = True
        inv = game.state.get_investigator("inv1")
        inv.horror = 2
        game.chaos_bag.tokens = [ChaosTokenType.SKULL]

        game.skill_test_engine.run_test(
            investigator_id="inv1",
            skill_type=Skill.WILLPOWER,
            difficulty=1,
        )
        assert inv.horror == 2
