"""Tests for .45 Automatic (Level 0)."""

import pytest
from backend.cards.guardian.forty_five_automatic_lv0 import FortyFiveAutomatic
from backend.engine.game import Game
from backend.models.enums import Action, CardType, ChaosTokenType, PlayerClass, SlotType
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import make_enemy_data, make_investigator_data, make_location_data


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(combat=4)
    g.register_card_data(inv_data)

    loc = make_location_data()
    g.register_card_data(loc)

    auto_data = CardData(
        id="45_automatic_lv0", name=".45 Automatic", name_cn=".45自动手枪",
        type=CardType.ASSET, card_class=PlayerClass.GUARDIAN, cost=4,
        slots=[SlotType.HAND], traits=["item", "weapon", "firearm"],
        uses={"ammo": 4},
    )
    g.register_card_data(auto_data)

    enemy_data = make_enemy_data(fight=3, health=5)
    g.register_card_data(enemy_data)

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)

    g.card_registry.register_class(FortyFiveAutomatic)
    return g


def _equip_45(game):
    inv = game.state.get_investigator("inv1")
    instance_id = game.state.next_instance_id()
    card_inst = CardInstance(
        instance_id=instance_id, card_id="45_automatic_lv0",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND],
        uses={"ammo": 4},
    )
    game.state.cards_in_play[instance_id] = card_inst
    inv.play_area.append(instance_id)
    game.card_registry.activate_card("45_automatic_lv0", instance_id, game.event_bus)
    return instance_id


def _spawn_enemy(game):
    enemy = CardInstance(
        instance_id="enemy_1", card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play["enemy_1"] = enemy
    inv = game.state.get_investigator("inv1")
    inv.threat_area.append("enemy_1")
    return enemy


class TestFortyFiveAutomatic:
    def test_card_registered(self, game):
        assert "45_automatic_lv0" in game.card_registry.registered_cards

    def test_extra_damage(self, game):
        """.45 Auto deals base 1 + 1 extra = 2 damage."""
        auto_id = _equip_45(game)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1",
            weapon_instance_id=auto_id,
        )
        assert enemy.damage == 2

    def test_consumes_ammo(self, game):
        """Each successful attack uses 1 ammo."""
        auto_id = _equip_45(game)
        _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1",
            weapon_instance_id=auto_id,
        )
        card = game.state.get_card_instance(auto_id)
        assert card.uses["ammo"] == 3  # Started with 4, used 1

    def test_no_ammo_no_bonus(self, game):
        """Without ammo, no extra damage."""
        auto_id = _equip_45(game)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]

        # Drain all ammo
        card = game.state.get_card_instance(auto_id)
        card.uses["ammo"] = 0

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1",
            weapon_instance_id=auto_id,
        )
        # Only base damage, no ammo bonus
        assert enemy.damage == 1
