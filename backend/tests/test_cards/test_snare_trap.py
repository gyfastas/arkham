"""Tests for Snare Trap (Level 2)."""

import pytest
from backend.cards.survivor.snare_trap_lv2 import SnareTrap
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
    loc_b = make_location_data(id="loc_b", connections=["test_location"])
    g.register_card_data(loc_b)
    g.register_card_data(make_event_data(
        id="snare_trap_lv2", name="Snare Trap", cost=2,
        card_class=PlayerClass.SURVIVOR,
    ))
    g.register_card_data(make_enemy_data(id="ghoul"))
    g.register_card_data(make_enemy_data(id="elite_monster", keywords=["elite"]))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.add_location("loc_b", loc_b, clues=0)
    g.card_registry.register_class(SnareTrap)
    impl = SnareTrap("impl_1")
    impl.register(g.event_bus, "impl_1")
    return g


def _play(game):
    return _emit(game, GameEvent.CARD_PLAYED,
                 extra={"card_id": "snare_trap_lv2"})


def _add_enemy(game, instance_id, card_id="ghoul"):
    enemy = CardInstance(
        instance_id=instance_id, card_id=card_id,
        owner_id="scenario", controller_id="scenario",
    )
    game.state.cards_in_play[instance_id] = enemy
    return enemy


class TestSnareTrap:
    def test_card_registered(self, game):
        assert "snare_trap_lv2" in game.card_registry.registered_cards

    def test_attach_marks_your_location(self, game):
        ctx = _play(game)
        trap = game.state.scenario.vars["snare_trap"]
        assert trap["location_id"] == "test_location"
        assert trap["enemy_instance_id"] is None
        assert ctx.extra["snare_trap_location"] == "test_location"

    def test_traps_enemy_entering_engagement(self, game):
        """非精英敌人与地点上调查员交战：消耗、解除交战、叠加陷阱。"""
        _play(game)
        _add_enemy(game, "e1")
        inv = game.state.get_investigator("inv1")
        inv.threat_area.append("e1")  # 交战状态（事件前的状态）

        ctx = _emit(game, GameEvent.ENEMY_ENGAGED, enemy_id="e1")
        enemy = game.state.get_card_instance("e1")
        trap = game.state.scenario.vars["snare_trap"]
        assert ctx.extra["snare_trap_trapped"] == "e1"
        assert enemy.exhausted is True
        assert "e1" not in inv.threat_area
        assert "e1" in game.state.locations["test_location"].enemies
        assert trap["enemy_instance_id"] == "e1"

    def test_trapped_enemy_stays_exhausted_instead_of_readying(self, game):
        """被叠加敌人将要准备：改为丢弃陷阱（敌人保持消耗）。"""
        _play(game)
        _add_enemy(game, "e1")
        inv = game.state.get_investigator("inv1")
        inv.threat_area.append("e1")
        _emit(game, GameEvent.ENEMY_ENGAGED, enemy_id="e1")

        # upkeep：引擎先置 ready 再发 CARD_READIED
        enemy = game.state.get_card_instance("e1")
        enemy.exhausted = False
        ctx = _emit(game, GameEvent.CARD_READIED, target="e1")

        assert ctx.extra["snare_trap_discarded"] is True
        assert enemy.exhausted is True  # 重新横置 ≈ "将要准备时改为…"
        assert "snare_trap" not in game.state.scenario.vars

    def test_elite_enemy_not_trapped(self, game):
        _play(game)
        _add_enemy(game, "e1", card_id="elite_monster")
        inv = game.state.get_investigator("inv1")
        inv.threat_area.append("e1")

        ctx = _emit(game, GameEvent.ENEMY_ENGAGED, enemy_id="e1")
        enemy = game.state.get_card_instance("e1")
        assert "snare_trap_trapped" not in ctx.extra
        assert enemy.exhausted is False
        assert "e1" in inv.threat_area

    def test_enemy_at_other_location_not_trapped(self, game):
        """交战对象不在被叠加地点时不触发。"""
        _play(game)
        inv = game.state.get_investigator("inv1")
        inv.location_id = "loc_b"  # 调查员在另一地点
        _add_enemy(game, "e1")
        inv.threat_area.append("e1")

        ctx = _emit(game, GameEvent.ENEMY_ENGAGED, enemy_id="e1")
        assert "snare_trap_trapped" not in ctx.extra
        assert game.state.get_card_instance("e1").exhausted is False
