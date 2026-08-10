"""Tests for "I've had worse…" (Level 2). (05315)

快速。被造成伤害/恐惧时打出：取消至多2点，获得等量资源。
"""

import pytest
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import GameEvent, PlayerClass
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)

import importlib
_impl_mod = importlib.import_module("backend.cards.guardian.ive_had_worse…_lv2")
IveHadWorseLv2 = _impl_mod.IveHadWorseLv2


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_event_data(
        id="ive_had_worse…_lv2", name="I've had worse…", cost=0, fast=True,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=0)
    g.card_registry.register_class(IveHadWorseLv2)

    inv = g.state.get_investigator("inv1")
    inv.hand = ["ive_had_worse…_lv2"]
    inv.resources = 2
    g.card_registry.activate_card("ive_had_worse…_lv2", "ihw_1", g.event_bus)
    return g


def _emit(game, event, amount):
    ctx = EventContext(
        game_state=game.state, event=event,
        investigator_id="inv1", amount=amount,
    )
    game.event_bus.emit(ctx)
    return ctx


class TestIveHadWorseLv2:
    def test_cancels_up_to_2_and_gains_resources(self, game):
        """3点伤害：取消2点，获得2资源。"""
        inv = game.state.get_investigator("inv1")
        ctx = _emit(game, GameEvent.DAMAGE_ASSIGNED, 3)
        assert ctx.amount == 1
        assert ctx.extra["ive_had_worse_cancelled"] == 2
        assert "ive_had_worse…_lv2" in inv.discard
        assert inv.resources == 2 + 2  # 费用0，+2

    def test_cancels_horror(self, game):
        """恐惧同样触发取消。"""
        inv = game.state.get_investigator("inv1")
        ctx = _emit(game, GameEvent.HORROR_ASSIGNED, 1)
        assert ctx.amount == 0
        assert ctx.extra["ive_had_worse_cancelled"] == 1
        assert inv.resources == 3

    def test_no_trigger_without_card(self, game):
        """手牌没有本卡时不触发。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = []
        ctx = _emit(game, GameEvent.DAMAGE_ASSIGNED, 3)
        assert ctx.amount == 3
        assert inv.resources == 2
