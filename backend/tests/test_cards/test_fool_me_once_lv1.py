"""Tests for "Fool me once..." (Level 1). (06156)

打出时叠加一张刚结算完的诡计；之后任意调查员抽到该诡计副本时，
弃置本卡并取消其显现效果。
"""

import pytest
from backend.cards.guardian.fool_me_once_lv1 import FoolMeOnce
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import CardType, GameEvent, PlayerClass
from backend.models.state import CardData
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)


def _treachery(cid):
    return CardData(
        id=cid, name=cid, name_cn=cid, type=CardType.TREACHERY,
        card_class=PlayerClass.NEUTRAL,
    )


@pytest.fixture
def game():
    g = Game("test")
    g.chaos_bag.seed(42)
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    g.register_card_data(make_location_data())
    g.register_card_data(make_event_data(
        id="fool_me_once_lv1", name="Fool me once...", cost=1, fast=True,
        card_class=PlayerClass.GUARDIAN,
    ))
    g.register_card_data(_treachery("frozen_in_fear"))
    g.register_card_data(_treachery("dissonant_voices"))

    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", g.state.get_card_data("test_location"), clues=0)
    g.card_registry.register_class(FoolMeOnce)

    inv = g.state.get_investigator("inv1")
    inv.hand.append("fool_me_once_lv1")
    inv.resources = 3
    impl = g.card_registry.activate_card("fool_me_once_lv1", "fmo_1", g.event_bus)
    return g, impl


def _draw_encounter(game, card_id, investigator_id="inv1"):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.ENCOUNTER_CARD_DRAWN,
        investigator_id=investigator_id, extra={"card_id": card_id},
    )
    game.event_bus.emit(ctx)
    return ctx


class TestFoolMeOnce:
    def test_play_attaches_treachery(self, game):
        """打出：付费入场并叠加诡计。"""
        g, impl = game
        inv = g.state.get_investigator("inv1")
        instance_id = impl.play_attaching(g.state, "inv1", "frozen_in_fear")
        assert instance_id is not None
        assert instance_id in inv.play_area
        assert inv.resources == 2
        assert "fool_me_once_lv1" not in inv.hand
        assert g.state.scenario.vars["fool_me_once"][instance_id] == "frozen_in_fear"

    def test_cancels_copy_draw(self, game):
        """抽到被叠加诡计的副本：弃置本卡并取消显现。"""
        g, impl = game
        inv = g.state.get_investigator("inv1")
        instance_id = impl.play_attaching(g.state, "inv1", "frozen_in_fear")

        ctx = _draw_encounter(g, "frozen_in_fear")
        assert ctx.cancelled is True
        assert ctx.extra["fool_me_once_cancelled"] == "frozen_in_fear"
        assert g.state.scenario.vars["cancelled_encounter"] == "frozen_in_fear"
        # 本卡弃置离场
        assert instance_id not in inv.play_area
        assert instance_id not in g.state.cards_in_play
        assert "fool_me_once_lv1" in inv.discard

    def test_other_treachery_not_cancelled(self, game):
        """抽到非叠加诡计：不触发。"""
        g, impl = game
        inv = g.state.get_investigator("inv1")
        instance_id = impl.play_attaching(g.state, "inv1", "frozen_in_fear")

        ctx = _draw_encounter(g, "dissonant_voices")
        assert ctx.cancelled is False
        assert instance_id in inv.play_area
