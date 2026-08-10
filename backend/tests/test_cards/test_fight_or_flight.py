"""Tests for Fight or Flight (Level 0)."""

import pytest
from backend.cards.survivor.fight_or_flight_lv0 import FightOrFlight
from backend.models.enums import GameEvent, PlayerClass, Skill
from backend.engine.event_bus import EventContext
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
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
        id="fight_or_flight_lv0", name="Fight or Flight", cost=1,
        card_class=PlayerClass.SURVIVOR, fast=True,
    ))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(FightOrFlight)
    impl = FightOrFlight("impl_1")
    impl.register(g.event_bus, "impl_1")
    return g


def _play(game):
    return _emit(game, GameEvent.CARD_PLAYED,
                 extra={"card_id": "fight_or_flight_lv0"})


class TestFightOrFlight:
    def test_card_registered(self, game):
        assert "fight_or_flight_lv0" in game.card_registry.registered_cards

    def test_bonus_equals_horror_on_you(self, game):
        """打出后战斗/敏捷检定+X（X=身上恐惧）。"""
        inv = game.state.get_investigator("inv1")
        inv.horror = 2
        _play(game)

        ctx = _emit(game, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.COMBAT, amount=3)
        assert ctx.amount == 5
        ctx = _emit(game, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.AGILITY, amount=3)
        assert ctx.amount == 5

    def test_bonus_tracks_current_horror(self, game):
        """X 动态跟随当前恐惧数量。"""
        inv = game.state.get_investigator("inv1")
        inv.horror = 1
        _play(game)
        inv.horror = 4

        ctx = _emit(game, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.COMBAT, amount=3)
        assert ctx.amount == 7

    def test_no_bonus_to_other_skills(self, game):
        inv = game.state.get_investigator("inv1")
        inv.horror = 3
        _play(game)

        ctx = _emit(game, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.INTELLECT, amount=3)
        assert ctx.amount == 3

    def test_expires_at_round_end(self, game):
        inv = game.state.get_investigator("inv1")
        inv.horror = 3
        _play(game)
        _emit(game, GameEvent.ROUND_ENDS)

        ctx = _emit(game, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.COMBAT, amount=3)
        assert ctx.amount == 3

    def test_zero_horror_no_bonus(self, game):
        inv = game.state.get_investigator("inv1")
        inv.horror = 0
        _play(game)

        ctx = _emit(game, GameEvent.SKILL_VALUE_DETERMINED,
                    skill_type=Skill.COMBAT, amount=3)
        assert ctx.amount == 3
