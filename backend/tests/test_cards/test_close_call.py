"""Tests for Close Call (Level 2)."""

import pytest
from backend.cards.survivor.close_call_lv2 import CloseCall
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent, PlayerClass
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data, make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(id="close_call_lv2", cost=2, fast=True))
    g.register_card_data(make_enemy_data(id="test_enemy"))
    g.register_card_data(make_enemy_data(id="elite_enemy", keywords=["elite"]))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(CloseCall)
    return g


def _arm(game):
    impl = CloseCall("impl_close_call")
    impl.register(game.event_bus, "impl_close_call")
    inv = game.state.get_investigator("inv1")
    inv.hand = ["close_call_lv2"]
    inv.resources = 2
    return inv


def _spawn_evaded_enemy(game, instance_id, card_id="test_enemy"):
    """被躲避后的敌人：横置、未交战、在地点上。"""
    inst = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    inst.exhausted = True
    game.state.cards_in_play[instance_id] = inst
    game.state.get_location("test_location").enemies.append(instance_id)


def _emit_evaded(game, enemy_iid):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.ENEMY_EVADED,
        investigator_id="inv1", enemy_id=enemy_iid,
    )
    game.event_bus.emit(ctx)
    return ctx


class TestCloseCall:
    def test_card_registered(self, game):
        assert "close_call_lv2" in game.card_registry.registered_cards

    def test_shuffles_non_elite_enemy_into_encounter_deck(self, game):
        inv = _arm(game)
        _spawn_evaded_enemy(game, "enemy_1")

        ctx = _emit_evaded(game, "enemy_1")

        assert ctx.extra.get("close_call_shuffled") == "test_enemy"
        assert "test_enemy" in game.state.scenario.encounter_deck
        assert "enemy_1" not in game.state.cards_in_play
        assert "enemy_1" not in game.state.get_location("test_location").enemies
        assert "close_call_lv2" in inv.discard
        assert inv.resources == 0

    def test_no_trigger_on_elite(self, game):
        inv = _arm(game)
        _spawn_evaded_enemy(game, "enemy_1", card_id="elite_enemy")

        ctx = _emit_evaded(game, "enemy_1")

        assert "close_call_shuffled" not in ctx.extra
        assert "enemy_1" in game.state.get_location("test_location").enemies
        assert "close_call_lv2" in inv.hand
        assert inv.resources == 2

    def test_no_trigger_without_card_in_hand(self, game):
        inv = _arm(game)
        inv.hand = []
        _spawn_evaded_enemy(game, "enemy_1")

        ctx = _emit_evaded(game, "enemy_1")

        assert "close_call_shuffled" not in ctx.extra
        assert "enemy_1" in game.state.get_location("test_location").enemies
