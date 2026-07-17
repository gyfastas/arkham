"""Tests for Duke (Level 0) — "Ashcan" Pete signature ally."""

import pytest
from backend.cards.neutral.duke_lv0 import Duke
from backend.engine.game import Game
from backend.models.enums import Action, CardType, ChaosTokenType, PlayerClass, SlotType
from backend.models.state import CardData, CardInstance
from backend.tests.conftest import make_enemy_data, make_investigator_data, make_location_data


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(combat=2, intellect=2)
    g.register_card_data(inv_data)

    loc = make_location_data(shroud=3, clue_value=2)
    g.register_card_data(loc)

    loc2 = make_location_data(id="test_location_2", shroud=2, clue_value=1)
    loc2.connections = ["test_location"]
    loc.connections = ["test_location_2"]
    g.register_card_data(loc2)

    duke_data = CardData(
        id="duke_lv0", name="Duke", name_cn="杜克",
        type=CardType.ASSET, card_class=PlayerClass.NEUTRAL, cost=2,
        slots=[], traits=["ally", "creature"], health=2, sanity=3,
        unique=True,
    )
    g.register_card_data(duke_data)

    enemy_data = make_enemy_data(fight=3, health=5)
    g.register_card_data(enemy_data)

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=2)
    g.add_location("test_location_2", loc2, clues=1)

    g.card_registry.register_class(Duke)
    return g


def _equip_duke(game):
    inv = game.state.get_investigator("inv1")
    instance_id = game.state.next_instance_id()
    card_inst = CardInstance(
        instance_id=instance_id, card_id="duke_lv0",
        owner_id="inv1", controller_id="inv1",
    )
    game.state.cards_in_play[instance_id] = card_inst
    inv.play_area.append(instance_id)
    game.card_registry.activate_card("duke_lv0", instance_id, game.event_bus)
    return instance_id


def _spawn_enemy(game, instance_id="enemy_1"):
    enemy = CardInstance(
        instance_id=instance_id, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    inv = game.state.get_investigator("inv1")
    inv.threat_area.append(instance_id)
    return enemy


def _get_impl(game, instance_id):
    return game.card_registry.active_instances[instance_id]


class TestDuke:
    def test_card_registered(self, game):
        assert "duke_lv0" in game.card_registry.registered_cards

    def test_activate_fight_base_skill_and_damage(self, game):
        """Duke fight: base combat treated as 4, +1 damage, exhausts Duke."""
        duke_id = _equip_duke(game)
        enemy = _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        impl = _get_impl(game, duke_id)
        ok = impl.activate_fight(game, "inv1", "enemy_1")

        assert ok
        # Base combat 2 -> treated as 4 vs fight 3: success.
        # Damage = 1 base + 1 duke bonus = 2
        assert enemy.damage == 2
        assert game.state.get_card_instance(duke_id).exhausted

    def test_activate_fight_fails_when_exhausted(self, game):
        """Cannot activate Duke while it is exhausted."""
        duke_id = _equip_duke(game)
        _spawn_enemy(game)
        game.state.get_card_instance(duke_id).exhausted = True

        impl = _get_impl(game, duke_id)
        assert impl.activate_fight(game, "inv1", "enemy_1") is False
        assert game.state.get_card_instance("enemy_1").damage == 0

    def test_activate_investigate_base_skill(self, game):
        """Duke investigate: base intellect treated as 4 (2 -> 4 vs shroud 3)."""
        duke_id = _equip_duke(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        inv = game.state.get_investigator("inv1")
        impl = _get_impl(game, duke_id)
        ok = impl.activate_investigate(game, "inv1")

        assert ok
        assert inv.clues == 1
        assert game.state.get_location("test_location").clues == 1
        assert game.state.get_card_instance(duke_id).exhausted

    def test_activate_investigate_with_move(self, game):
        """Duke investigate may move to a connecting location first."""
        duke_id = _equip_duke(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        inv = game.state.get_investigator("inv1")
        impl = _get_impl(game, duke_id)
        ok = impl.activate_investigate(game, "inv1", destination="test_location_2")

        assert ok
        assert inv.location_id == "test_location_2"
        # 4 vs shroud 2 -> success, discover 1 clue at new location
        assert inv.clues == 1

    def test_activate_investigate_invalid_destination(self, game):
        """Cannot move to a non-connecting location with Duke."""
        duke_id = _equip_duke(game)
        game.add_location("far_location", make_location_data(id="far_location"), clues=0)

        impl = _get_impl(game, duke_id)
        ok = impl.activate_investigate(game, "inv1", destination="far_location")

        assert ok is False
        assert not game.state.get_card_instance(duke_id).exhausted
