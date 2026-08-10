"""Tests for Hiding Spot (Level 0)."""

import pytest
from backend.cards.survivor.hiding_spot_lv0 import HidingSpot
from backend.models.enums import GameEvent, PlayerClass
from backend.engine.event_bus import EventContext
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_enemy_data, make_event_data, make_investigator_data,
    make_location_data,
)
from backend.engine.game import Game


def _emit(game, event, inv_id="inv1", **kwargs):
    ctx = EventContext(
        game_state=game.state, event=event, investigator_id=inv_id, **kwargs)
    game.event_bus.emit(ctx)
    return ctx


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="hiding_spot_lv0", name="Hiding Spot", cost=1,
        card_class=PlayerClass.SURVIVOR, fast=True,
    ))
    g.register_card_data(make_enemy_data())
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(HidingSpot)
    impl = HidingSpot("impl_1")
    impl.register(g.event_bus, "impl_1")
    return g


def _play(game, **extra):
    return _emit(game, GameEvent.CARD_PLAYED,
                 extra={"card_id": "hiding_spot_lv0", **extra})


def _add_enemy(game, instance_id="e1", exhausted=False, engaged=False):
    enemy = CardInstance(
        instance_id=instance_id, card_id="test_enemy",
        owner_id="scenario", controller_id="scenario",
        exhausted=exhausted,
    )
    game.state.cards_in_play[instance_id] = enemy
    if engaged:
        game.state.get_investigator("inv1").threat_area.append(instance_id)
    else:
        game.state.locations["test_location"].enemies.append(instance_id)
    return enemy


class TestHidingSpot:
    def test_card_registered(self, game):
        assert "hiding_spot_lv0" in game.card_registry.registered_cards

    def test_attach_marks_location(self, game):
        """打出：默认叠加到你所在地点。"""
        ctx = _play(game)
        assert ctx.extra["hiding_spot_location"] == "test_location"
        assert "test_location" in game.state.scenario.vars["hiding_spot_locations"]

    def test_attach_to_explicit_location(self, game):
        """可叠加到任意地点（ctx.extra 指定）。"""
        loc_b = make_location_data(id="loc_b")
        game.register_card_data(loc_b)
        game.add_location("loc_b", loc_b)

        ctx = _play(game, location_id="loc_b")
        assert ctx.extra["hiding_spot_location"] == "loc_b"
        assert "loc_b" in game.state.scenario.vars["hiding_spot_locations"]

    def test_discarded_when_ready_enemy_at_location(self, game):
        """敌军阶段结束时地点上有准备的敌人：丢弃藏身地点。"""
        _play(game)
        _add_enemy(game, exhausted=False)

        ctx = _emit(game, GameEvent.ENEMY_PHASE_ENDS)
        assert ctx.extra.get("hiding_spot_discarded") == "test_location"
        assert "test_location" not in \
            game.state.scenario.vars["hiding_spot_locations"]

    def test_discarded_by_ready_engaged_enemy(self, game):
        """与地点上调查员交战的准备敌人同样触发强制弃牌。"""
        _play(game)
        _add_enemy(game, exhausted=False, engaged=True)

        _emit(game, GameEvent.ENEMY_PHASE_ENDS)
        assert "test_location" not in \
            game.state.scenario.vars["hiding_spot_locations"]

    def test_survives_when_enemies_exhausted(self, game):
        """地点上敌人全部横置时不弃牌。"""
        _play(game)
        _add_enemy(game, exhausted=True)

        ctx = _emit(game, GameEvent.ENEMY_PHASE_ENDS)
        assert "hiding_spot_discarded" not in ctx.extra
        assert "test_location" in game.state.scenario.vars["hiding_spot_locations"]
