"""Tests for .18 Derringer (Level 0)."""

import pytest
from backend.cards.survivor.eighteen_derringer_lv0 import EighteenDerringer
from backend.engine.game import Game
from backend.models.enums import Action, CardType, ChaosTokenType, PlayerClass, SlotType
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import make_enemy_data, make_investigator_data, make_location_data


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(combat=3)
    g.register_card_data(inv_data)

    loc = make_location_data()
    g.register_card_data(loc)

    derringer_data = CardData(
        id="18_derringer_lv0", name=".18 Derringer", name_cn=".18大口径短口手枪",
        type=CardType.ASSET, card_class=PlayerClass.SURVIVOR, cost=3,
        slots=[SlotType.HAND], traits=["item", "weapon", "firearm", "illicit"],
        uses={"ammo": 2},
    )
    g.register_card_data(derringer_data)

    enemy_data = make_enemy_data(fight=3, health=5)
    g.register_card_data(enemy_data)

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)

    g.card_registry.register_class(EighteenDerringer)
    return g


def _equip_derringer(game):
    inv = game.state.get_investigator("inv1")
    instance_id = game.state.next_instance_id()
    card_inst = CardInstance(
        instance_id=instance_id, card_id="18_derringer_lv0",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.HAND],
        uses={"ammo": 2},
    )
    game.state.cards_in_play[instance_id] = card_inst
    inv.play_area.append(instance_id)
    game.card_registry.activate_card("18_derringer_lv0", instance_id, game.event_bus)
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


class TestEighteenDerringer:
    def test_card_registered(self, game):
        assert "18_derringer_lv0" in game.card_registry.registered_cards

    def test_combat_bonus(self, game):
        """Derringer gives +2 combat."""
        derringer_id = _equip_derringer(game)
        enemy = _spawn_enemy(game)
        # +2 combat: base 3 + 2 = 5 vs fight 3, need to succeed
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1",
            weapon_instance_id=derringer_id,
        )
        # base 1 + 1 extra = 2 damage
        assert enemy.damage == 2

    def test_consumes_ammo(self, game):
        derringer_id = _equip_derringer(game)
        _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1",
            weapon_instance_id=derringer_id,
        )
        card = game.state.get_card_instance(derringer_id)
        assert card.uses["ammo"] == 1  # Started with 2, used 1

    def test_refund_ammo_on_fail(self, game):
        """On a failed attack, 1 ammo is returned."""
        derringer_id = _equip_derringer(game)
        _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1",
            weapon_instance_id=derringer_id,
        )
        card = game.state.get_card_instance(derringer_id)
        # No ammo was spent (DAMAGE_DEALT doesn't fire on fail),
        # but refund still fires → 2 + 1 = 3
        assert card.uses["ammo"] == 3

    def test_no_bonus_without_ammo(self, game):
        derringer_id = _equip_derringer(game)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.PLUS_1]

        card = game.state.get_card_instance(derringer_id)
        card.uses["ammo"] = 0

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1",
            weapon_instance_id=derringer_id,
        )
        # Only base damage, no extra
        assert enemy.damage == 1
