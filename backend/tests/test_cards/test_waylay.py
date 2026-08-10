"""Tests for Waylay (Level 0)."""

import pytest
from backend.cards.survivor.waylay_lv0 import Waylay
from backend.models.enums import ChaosTokenType, GameEvent, PlayerClass
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
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data(agility=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(
        id="waylay_lv0", name="Waylay", cost=3,
        card_class=PlayerClass.SURVIVOR,
    ))
    g.register_card_data(make_enemy_data(id="ghoul", evade=3))
    g.register_card_data(make_enemy_data(id="elite_monster", evade=2,
                                         keywords=["elite"]))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(Waylay)
    # 与生产一致：activate_card 注入 chaos_bag（CardSelfTest.bind_chaos_bag）
    g.card_registry.activate_card(
        "waylay_lv0", "impl_1", g.event_bus, chaos_bag=g.chaos_bag)
    return g


def _add_enemy(game, instance_id, card_id="ghoul", exhausted=True,
               engaged=False):
    enemy = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
        exhausted=exhausted,
    )
    game.state.cards_in_play[instance_id] = enemy
    if engaged:
        game.state.get_investigator("inv1").threat_area.append(instance_id)
    else:
        game.state.locations["test_location"].enemies.append(instance_id)
    return enemy


def _play(game, **extra):
    game.chaos_bag.tokens = extra.pop("tokens", [ChaosTokenType.ZERO])
    return _emit(game, GameEvent.CARD_PLAYED,
                 extra={"card_id": "waylay_lv0", **extra})


class TestWaylay:
    def test_card_registered(self, game):
        assert "waylay_lv0" in game.card_registry.registered_cards

    def test_success_defeats_exhausted_enemy(self, game):
        """敏捷3+0 对 躲避3：成功，敌人被击败。"""
        _add_enemy(game, "e1")

        ctx = _play(game)
        assert ctx.extra["waylay_success"] is True
        assert ctx.extra["waylay_target"] == "e1"
        assert game.state.get_card_instance("e1") is None
        assert "ghoul" in game.state.scenario.encounter_discard
        assert "e1" not in game.state.locations["test_location"].enemies

    def test_failure_leaves_enemy(self, game):
        """敏捷3-2=1 对 躲避3：失败，敌人留存。"""
        _add_enemy(game, "e1")

        ctx = _play(game, tokens=[ChaosTokenType.MINUS_2])
        assert ctx.extra["waylay_success"] is False
        assert game.state.get_card_instance("e1") is not None

    def test_ignores_ready_enemies(self, game):
        """没有消耗的敌人时不发动（准备的敌人不是合法目标）。"""
        _add_enemy(game, "e1", exhausted=False)

        ctx = _play(game)
        assert "waylay_success" not in ctx.extra
        assert game.state.get_card_instance("e1") is not None

    def test_ignores_elite_enemies(self, game):
        _add_enemy(game, "e1", card_id="elite_monster", exhausted=True)

        ctx = _play(game)
        assert "waylay_success" not in ctx.extra
        assert game.state.get_card_instance("e1") is not None

    def test_can_target_engaged_exhausted_enemy(self, game):
        """与你交战的消耗敌人也是合法目标。"""
        _add_enemy(game, "e1", exhausted=True, engaged=True)
        inv = game.state.get_investigator("inv1")

        ctx = _play(game)
        assert ctx.extra["waylay_success"] is True
        assert "e1" not in inv.threat_area
        assert game.state.get_card_instance("e1") is None
