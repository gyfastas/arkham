"""Tests for "Look what I found!" (Level 0)."""

import pytest
from backend.cards.survivor.look_what_i_found_lv0 import LookWhatIFound
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent, PlayerClass, Skill
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data()
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(id="look_what_i_found_lv0", cost=2, fast=True))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=2)
    g.card_registry.register_class(LookWhatIFound)
    return g


def _arm(game):
    impl = LookWhatIFound("impl_lwif")
    impl.register(game.event_bus, "impl_lwif")
    inv = game.state.get_investigator("inv1")
    inv.hand = ["look_what_i_found_lv0"]
    inv.resources = 2
    return inv


def _fail(game, skill_type, difficulty, modified_skill):
    ctx = EventContext(
        game_state=game.state, event=GameEvent.SKILL_TEST_FAILED,
        investigator_id="inv1", success=False,
        skill_type=skill_type, difficulty=difficulty,
        modified_skill=modified_skill,
    )
    game.event_bus.emit(ctx)
    return ctx


class TestLookWhatIFound:
    def test_card_registered(self, game):
        assert "look_what_i_found_lv0" in game.card_registry.registered_cards

    def test_discovers_2_clues_on_investigate_fail_by_2_or_less(self, game):
        inv = _arm(game)
        ctx = _fail(game, Skill.INTELLECT, difficulty=3, modified_skill=2)

        assert ctx.extra.get("look_what_i_found_clues") == 2
        assert inv.clues == 2
        assert game.state.get_location("test_location").clues == 0
        assert inv.resources == 0
        assert "look_what_i_found_lv0" in inv.discard

    def test_no_trigger_when_margin_over_2(self, game):
        inv = _arm(game)
        ctx = _fail(game, Skill.INTELLECT, difficulty=5, modified_skill=2)

        assert "look_what_i_found_clues" not in ctx.extra
        assert inv.clues == 0
        assert "look_what_i_found_lv0" in inv.hand

    def test_no_trigger_on_non_investigate_test(self, game):
        inv = _arm(game)
        ctx = _fail(game, Skill.COMBAT, difficulty=3, modified_skill=2)

        assert "look_what_i_found_clues" not in ctx.extra
        assert inv.clues == 0
        assert "look_what_i_found_lv0" in inv.hand
