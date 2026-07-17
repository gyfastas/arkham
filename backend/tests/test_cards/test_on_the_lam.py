"""Tests for On the Lam — "Skids" O'Toole signature event."""

import pytest
from backend.cards.neutral.on_the_lam import OnTheLam
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import Action, GameEvent
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data, make_location_data,
)


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data()
    g.register_card_data(inv_data)

    loc = make_location_data()
    g.register_card_data(loc)

    event_data = make_event_data(id="on_the_lam", name="On the Lam", cost=1, fast=True)
    g.register_card_data(event_data)

    g.register_card_data(make_enemy_data(id="thug", fight=3, damage=1, horror=1))
    g.register_card_data(
        make_enemy_data(id="boss", fight=4, damage=1, horror=1, keywords=["elite"])
    )

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)

    g.card_registry.register_class(OnTheLam)
    return g


def _play_on_the_lam(game):
    inv = game.state.get_investigator("inv1")
    inv.hand = ["on_the_lam"]
    inv.resources = 5
    inv.actions_remaining = 3
    ok = game.action_resolver.perform_action("inv1", Action.PLAY, card_id="on_the_lam")
    assert ok
    return inv


def _spawn_enemy(game, card_id, instance_id):
    enemy = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    inv = game.state.get_investigator("inv1")
    inv.threat_area.append(instance_id)
    return enemy


class TestOnTheLam:
    def test_card_registered(self, game):
        assert "on_the_lam" in game.card_registry.registered_cards

    def test_non_elite_enemy_cannot_attack(self, game):
        """Until end of round, engaged non-Elite enemies do not attack you."""
        inv = _play_on_the_lam(game)
        enemy = _spawn_enemy(game, "thug", "enemy_1")

        game.enemy_phase.resolve()

        assert inv.damage == 0
        assert inv.horror == 0
        assert enemy.exhausted  # prevented from attacking

    def test_elite_enemy_still_attacks(self, game):
        """Elite enemies are unaffected."""
        inv = _play_on_the_lam(game)
        _spawn_enemy(game, "boss", "enemy_1")

        game.enemy_phase.resolve()

        assert inv.damage == 1
        assert inv.horror == 1

    def test_attack_of_opportunity_cancelled(self, game):
        """Non-Elite enemies cannot make attacks of opportunity against you."""
        inv = _play_on_the_lam(game)
        _spawn_enemy(game, "thug", "enemy_1")
        inv.deck = ["c1"]

        # DRAW is not AoO-exempt; would normally provoke an attack
        ok = game.action_resolver.perform_action("inv1", Action.DRAW)
        assert ok
        assert inv.damage == 0
        assert inv.horror == 0

    def test_effect_expires_at_round_end(self, game):
        """Effect ends at the end of the round."""
        inv = _play_on_the_lam(game)
        assert getattr(inv, "active_effects", {}).get("on_the_lam") is True

        ctx = EventContext(game_state=game.state, event=GameEvent.ROUND_ENDS)
        game.event_bus.emit(ctx)

        assert not getattr(inv, "active_effects", {}).get("on_the_lam")

        # Next round the enemy attacks normally again
        enemy = _spawn_enemy(game, "thug", "enemy_1")
        game.enemy_phase.resolve()
        assert inv.damage == 1
