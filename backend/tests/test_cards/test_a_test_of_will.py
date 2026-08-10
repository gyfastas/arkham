"""Tests for A Test of Will (Level 1)."""

import pytest
from backend.cards.survivor.a_test_of_will_lv1 import ATestOfWill
from backend.models.enums import CardType, GameEvent, PlayerClass
from backend.engine.event_bus import EventContext
from backend.models.state import CardData
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)
from backend.engine.game import Game


def _treachery(cid: str, subtype: str = "") -> CardData:
    return CardData(
        id=cid, name=cid, name_cn=cid, type=CardType.TREACHERY,
        card_class=PlayerClass.NEUTRAL, subtype=subtype,
    )


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
        id="a_test_of_will_lv1", name="A Test of Will", cost=1,
        card_class=PlayerClass.SURVIVOR, fast=True,
    ))
    g.register_card_data(_treachery("frozen_in_fear"))
    g.register_card_data(_treachery("dark_memory", subtype="weakness"))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(ATestOfWill)
    impl = ATestOfWill("impl_1")
    impl.register(g.event_bus, "impl_1")
    return g


def _draw_encounter(game, card_id, inv_id="inv1"):
    return _emit(game, GameEvent.ENCOUNTER_CARD_DRAWN, inv_id,
                 extra={"card_id": card_id})


class TestATestOfWill:
    def test_card_registered(self, game):
        assert "a_test_of_will_lv1" in game.card_registry.registered_cards

    def test_cancels_non_weakness_treachery_and_exiles(self, game):
        """抽到非弱点诡计：自动打出、标记取消、放逐（不入弃牌堆）。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["a_test_of_will_lv1"]
        inv.resources = 1

        ctx = _draw_encounter(game, "frozen_in_fear")
        assert ctx.extra["a_test_of_will_cancelled"] == "frozen_in_fear"
        assert game.state.scenario.vars["cancelled_encounter"] == "frozen_in_fear"
        assert "a_test_of_will_lv1" in game.state.scenario.vars["exiled_cards"]
        assert "a_test_of_will_lv1" not in inv.discard
        assert "a_test_of_will_lv1" not in inv.hand
        assert inv.resources == 0

    def test_ignores_weakness_treachery(self, game):
        """弱点诡计卡不触发。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["a_test_of_will_lv1"]
        inv.resources = 1

        ctx = _draw_encounter(game, "dark_memory")
        assert "a_test_of_will_cancelled" not in ctx.extra
        assert "a_test_of_will_lv1" in inv.hand
        assert inv.resources == 1

    def test_ignores_enemy_cards(self, game):
        """非诡计卡不触发。"""
        inv = game.state.get_investigator("inv1")
        inv.hand = ["a_test_of_will_lv1"]
        inv.resources = 1
        game.register_card_data(make_event_data(id="some_event"))

        ctx = _draw_encounter(game, "some_event")
        assert "a_test_of_will_cancelled" not in ctx.extra

    def test_cancels_for_other_investigator_at_your_location(self, game):
        """同地点其他调查员抽到诡计卡时也能打出。"""
        inv2_data = make_investigator_data(id="inv2", name="Second")
        game.register_card_data(inv2_data)
        game.add_investigator("inv2", inv2_data, starting_location="test_location")
        inv1 = game.state.get_investigator("inv1")
        inv1.hand = ["a_test_of_will_lv1"]
        inv1.resources = 1

        ctx = _draw_encounter(game, "frozen_in_fear", inv_id="inv2")
        assert ctx.extra["a_test_of_will_cancelled"] == "frozen_in_fear"
        assert inv1.resources == 0
        assert "a_test_of_will_lv1" in game.state.scenario.vars["exiled_cards"]

    def test_no_trigger_without_resources(self, game):
        inv = game.state.get_investigator("inv1")
        inv.hand = ["a_test_of_will_lv1"]
        inv.resources = 0

        ctx = _draw_encounter(game, "frozen_in_fear")
        assert "a_test_of_will_cancelled" not in ctx.extra
        assert "a_test_of_will_lv1" in inv.hand
