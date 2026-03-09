"""Tests for Beat Cop (Level 0)."""

import pytest
from backend.cards.guardian.beat_cop_lv0 import BeatCop
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

    beat_cop_data = CardData(
        id="beat_cop_lv0", name="Beat Cop", name_cn="巡警",
        type=CardType.ASSET, card_class=PlayerClass.GUARDIAN, cost=4,
        slots=[SlotType.ALLY], traits=["ally", "police"],
        skill_icons={"combat": 1},
    )
    g.register_card_data(beat_cop_data)

    enemy_data = make_enemy_data(fight=3, health=4)
    g.register_card_data(enemy_data)

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)

    g.card_registry.register_class(BeatCop)
    return g


def _equip_beat_cop(game):
    inv = game.state.get_investigator("inv1")
    instance_id = game.state.next_instance_id()
    card_inst = CardInstance(
        instance_id=instance_id, card_id="beat_cop_lv0",
        owner_id="inv1", controller_id="inv1",
        slot_used=[SlotType.ALLY],
    )
    game.state.cards_in_play[instance_id] = card_inst
    inv.play_area.append(instance_id)
    game.card_registry.activate_card("beat_cop_lv0", instance_id, game.event_bus)
    return instance_id


class TestBeatCop:
    def test_card_registered(self, game):
        assert "beat_cop_lv0" in game.card_registry.registered_cards

    def test_combat_bonus(self, game):
        """Beat Cop provides +1 combat during fight."""
        _equip_beat_cop(game)
        _spawn_enemy(game)
        game.chaos_bag.tokens = [ChaosTokenType.ZERO]

        inv = game.state.get_investigator("inv1")
        inv.actions_remaining = 3

        # Combat 3 + 1 beat cop = 4 vs fight 3 -> success
        game.action_resolver.perform_action(
            "inv1", Action.FIGHT,
            enemy_instance_id="enemy_1",
        )
        enemy = game.state.get_card_instance("enemy_1")
        assert enemy.damage > 0


def _spawn_enemy(game, instance_id="enemy_1"):
    enemy = CardInstance(
        instance_id=instance_id, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    inv = game.state.get_investigator("inv1")
    inv.threat_area.append(instance_id)
    return enemy
