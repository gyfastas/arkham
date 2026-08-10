"""Tests for True Survivor (Level 3)."""

import pytest
from backend.cards.survivor.true_survivor_lv3 import TrueSurvivor
from backend.models.enums import CardType, GameEvent, PlayerClass
from backend.engine.event_bus import EventContext
from backend.models.state import CardData
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)
from backend.engine.game import Game


def _skill(cid: str, traits: list[str]) -> CardData:
    return CardData(
        id=cid, name=cid, name_cn=cid, type=CardType.SKILL,
        card_class=PlayerClass.SURVIVOR, traits=traits,
        skill_icons={"wild": 1},
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
        id="true_survivor_lv3", name="True Survivor", cost=3,
        card_class=PlayerClass.SURVIVOR,
    ))
    g.register_card_data(_skill("resourceful_lv0", ["innate"]))
    g.register_card_data(_skill("not_without_a_fight_lv0", ["innate"]))
    g.register_card_data(_skill("guts_lv0", ["innate"]))
    g.register_card_data(_skill("fearless_lv0", ["innate"]))
    g.register_card_data(_skill("manual_dexterity_lv0", ["practiced"]))
    g.register_card_data(make_event_data(id="lucky_lv0", name="Lucky!"))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(TrueSurvivor)
    impl = TrueSurvivor("impl_1")
    impl.register(g.event_bus, "impl_1")
    return g


def _play(game):
    return _emit(game, GameEvent.CARD_PLAYED,
                 extra={"card_id": "true_survivor_lv3"})


class TestTrueSurvivor:
    def test_card_registered(self, game):
        assert "true_survivor_lv3" in game.card_registry.registered_cards

    def test_returns_up_to_3_innate_skills(self, game):
        """弃牌堆4张天性技能卡：只返回前3张。"""
        inv = game.state.get_investigator("inv1")
        inv.discard = [
            "resourceful_lv0", "not_without_a_fight_lv0",
            "guts_lv0", "fearless_lv0",
        ]

        ctx = _play(game)
        returned = ctx.extra["true_survivor_returned"]
        assert returned == [
            "resourceful_lv0", "not_without_a_fight_lv0", "guts_lv0"]
        assert "fearless_lv0" in inv.discard
        for cid in returned:
            assert cid in inv.hand
            assert cid not in inv.discard

    def test_skips_non_innate_and_non_skill(self, game):
        """非天性技能卡与非技能卡不返回。"""
        inv = game.state.get_investigator("inv1")
        inv.discard = ["manual_dexterity_lv0", "lucky_lv0", "resourceful_lv0"]

        ctx = _play(game)
        assert ctx.extra["true_survivor_returned"] == ["resourceful_lv0"]
        assert "manual_dexterity_lv0" in inv.discard
        assert "lucky_lv0" in inv.discard
        assert "resourceful_lv0" in inv.hand

    def test_empty_discard_returns_nothing(self, game):
        inv = game.state.get_investigator("inv1")
        inv.discard = []

        ctx = _play(game)
        assert ctx.extra["true_survivor_returned"] == []
        assert inv.hand == []
