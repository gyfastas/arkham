"""Tests for Will to Survive (Level 3)."""

import pytest
from backend.cards.survivor.will_to_survive_lv3 import WillToSurvive
from backend.engine.event_bus import EventContext
from backend.models.enums import Action, ChaosTokenType, GameEvent, PlayerClass, Skill
from backend.tests.conftest import (
    make_event_data, make_investigator_data, make_location_data,
)
from backend.engine.game import Game


@pytest.fixture
def game():
    g = Game("test")
    inv_data = make_investigator_data(willpower=3)
    g.register_card_data(inv_data)
    loc = make_location_data()
    g.register_card_data(loc)
    g.register_card_data(make_event_data(id="will_to_survive_lv3", cost=4, fast=True))
    g.add_investigator("inv1", inv_data, starting_location="test_location")
    g.add_location("test_location", loc, clues=0)
    g.card_registry.register_class(WillToSurvive)
    return g


def _play(game):
    inv = game.state.get_investigator("inv1")
    inv.hand = ["will_to_survive_lv3"]
    inv.resources = 4
    ok = game.action_resolver.perform_action(
        "inv1", Action.PLAY, card_id="will_to_survive_lv3")
    assert ok
    return inv


class TestWillToSurvive:
    def test_card_registered(self, game):
        assert "will_to_survive_lv3" in game.card_registry.registered_cards

    def test_token_modifier_skipped(self, game):
        """打出后：本回合技能检定不揭示混沌标记（修正归零）。"""
        _play(game)
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_3]

        result = game.skill_test_engine.run_test("inv1", Skill.WILLPOWER, 1)

        assert result.token_modifier == 0
        assert result.modified_skill == 3
        assert result.success is True

    def test_auto_fail_ignored(self, game):
        """不揭示标记即无自动失败：按技能值对难度结算。"""
        _play(game)
        game.chaos_bag.tokens = [ChaosTokenType.AUTO_FAIL]

        result = game.skill_test_engine.run_test("inv1", Skill.WILLPOWER, 2)

        assert result.success is True  # 3 >= 2

    def test_expires_at_own_turn_end(self, game):
        """直到你的回合结束：自己回合结束后标记照常揭示。"""
        inv = _play(game)
        game.event_bus.emit(EventContext(
            game_state=game.state,
            event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="inv1",
        ))
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_3]

        result = game.skill_test_engine.run_test("inv1", Skill.WILLPOWER, 1)

        assert result.token_modifier == -3
        assert result.success is False

    def test_other_turn_end_does_not_expire(self, game):
        """其他调查员的回合结束不清除效果。"""
        _play(game)
        game.event_bus.emit(EventContext(
            game_state=game.state,
            event=GameEvent.INVESTIGATOR_TURN_ENDS,
            investigator_id="inv2",
        ))
        game.chaos_bag.tokens = [ChaosTokenType.MINUS_3]

        result = game.skill_test_engine.run_test("inv1", Skill.WILLPOWER, 1)

        assert result.token_modifier == 0
        assert result.success is True
